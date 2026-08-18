#!/usr/bin/env python3
"""Standalone face-seeker tests (no pytest — run with .venv/bin/python tests/test_seeker.py).

Covers: ScanMove trajectory, sweep pattern, and the FaceSeeker state machine
(loss trigger, leg sequencing, abort on face, cooldown). Robot-free: the SDK
Move base class falls back to a stub inside hub.seeker when reachy_mini is
absent, and ticks are driven directly instead of running the thread.
"""

import math
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from hub.seeker import FaceSeeker, ScanMove, scan_targets  # noqa: E402

PASSED = 0


def ok(cond: bool, label: str) -> None:
    global PASSED
    assert cond, f"FAIL: {label}"
    PASSED += 1
    print(f"  ok: {label}")


class Face:
    def __init__(self, detected: bool):
        self.detected = detected


class StubRobot:
    def __init__(self):
        self.face = Face(False)

    def get_tracked_face(self, wait: bool = False):
        return self.face


class StubState:
    current_move = None


class StubManager:
    def __init__(self):
        self.queued = []
        self.move_queue = []
        self.state = StubState()
        self._head_tracking = False
        self._is_listening = False
        self.idle = True

    def queue_move(self, move):
        self.queued.append(move)
        self.move_queue.append(move)

    def is_idle(self):
        return self.idle

    def set_head_tracking(self, enabled):
        self._head_tracking = enabled


def make_seeker(robot, manager, **kw):
    kw.setdefault("lost_after_s", 8.0)
    kw.setdefault("cooldown_s", 90.0)
    s = FaceSeeker(robot, manager, **kw)
    return s


# ── ScanMove ────────────────────────────────────────────────────────────────

print("ScanMove")
m = ScanMove(0.0, math.radians(60.0), speed_dps=30.0, hold_s=1.0)
ok(abs(m.travel_s - 2.0) < 1e-9, "travel time = delta/speed (60deg @ 30dps = 2s)")
ok(abs(m.duration - 3.0) < 1e-9, "duration includes hold")
_, _, yaw0 = m.evaluate(0.0)
ok(abs(yaw0 - 0.0) < 1e-9, "starts at start_yaw")
_, _, yaw_end = m.evaluate(m.travel_s + 0.5)
ok(abs(yaw_end - math.radians(60.0)) < 1e-9, "holds target after travel")
_, _, yaw_mid = m.evaluate(1.0)
ok(0.0 < yaw_mid < math.radians(60.0), "eases through intermediate yaw")

targets = scan_targets(0.0)
ok(targets[-1] == 0.0, "sweep ends recentered")
ok(abs(targets[0]) == math.radians(60.0) and abs(targets[-2]) == math.radians(150.0), "widening sweep 60->150deg")
ok(all(abs(t) <= math.radians(150.0) for t in targets), "all targets within body-yaw limit")

# ── seeker state machine ────────────────────────────────────────────────────

print("seeker state machine")
robot = StubRobot()
mgr = StubManager()
s = make_seeker(robot, mgr)
mgr._head_tracking = True

# face present: no scanning
robot.face = Face(True)
s._tick()
ok(not s._scanning and not mgr.queued, "face present -> no scan")

# face lost but not long enough
robot.face = Face(False)
s._last_seen = time.monotonic() - 3.0
s._tick()
ok(not s._scanning, "short loss -> no scan yet")

# sustained loss -> scan starts, first leg queued
s._last_seen = time.monotonic() - 10.0
s._tick()
ok(s._scanning and len(mgr.queued) == 1, "sustained loss -> scan starts")
ok(abs(s.hold_yaw) == math.radians(60.0), "hold_yaw anchors at leg target")

# leg still playing -> no second leg
mgr.state.current_move = mgr.queued[-1]
mgr.move_queue.clear()
s._tick()
ok(len(mgr.queued) == 1, "no new leg while one is playing")

# leg finished -> next leg
mgr.state.current_move = None
s._tick()
ok(len(mgr.queued) == 2, "next leg queued when previous done")

# face found mid-scan -> abort, no further legs
robot.face = Face(True)
s._tick()
ok(not s._scanning, "face found -> scan aborted")
robot.face = Face(False)
mgr.state.current_move = None
s._tick()
ok(len(mgr.queued) == 2, "no legs right after abort (fresh loss timer)")

# exhausted sweep -> cooldown
robot.face = Face(False)
s2 = make_seeker(StubRobot(), mgr2 := StubManager())
mgr2._head_tracking = True
s2._last_seen = time.monotonic() - 10.0
s2._tick()
while s2._scanning:
    mgr2.state.current_move = None
    mgr2.move_queue.clear()
    s2._tick()
ok(len(mgr2.queued) == len(scan_targets(0.0)), "full sweep queues every target once")
ok(s2._cooldown_until > time.monotonic(), "cooldown set after empty sweep")
s2._last_seen = time.monotonic() - 100.0
n_before = len(mgr2.queued)
s2._tick()
ok(len(mgr2.queued) == n_before, "no rescan during cooldown")

# tracking off -> never scan
s3 = make_seeker(StubRobot(), mgr3 := StubManager())
mgr3._head_tracking = False
s3._last_seen = time.monotonic() - 100.0
s3._tick()
ok(not s3._scanning, "tracking disabled -> no scan")

# not idle -> no scan start
s4 = make_seeker(StubRobot(), mgr4 := StubManager())
mgr4._head_tracking = True
mgr4.idle = False
s4._last_seen = time.monotonic() - 100.0
s4._tick()
ok(not s4._scanning, "busy manager -> no scan start")

# listening mid-scan -> abort
s5 = make_seeker(StubRobot(), mgr5 := StubManager())
mgr5._head_tracking = True
s5._last_seen = time.monotonic() - 100.0
s5._tick()
mgr5.state.current_move = None
mgr5.move_queue.clear()
mgr5._is_listening = True
s5._tick()
ok(not s5._scanning, "listening interrupts scan")

print(f"\nALL {PASSED} CHECKS PASSED")
