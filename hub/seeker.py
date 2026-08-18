"""Look for humans: body-yaw scan when the face tracker loses everyone.

The daemon-side face tracker (reachy_mini >= 1.9.0) only steers the HEAD, and
the head can only deviate ~65 deg from the body. So when nobody is in frame,
this module slowly sweeps the body yaw in widening legs until the tracker
reports a face again, then anchors the body where the person was found.

Integration (see scripts/launch_patched.py):
- ``FaceSeeker`` is a daemon thread polling ``robot.get_tracked_face``.
- Scan legs are queued as regular ``Move`` objects on the upstream
  ``MovementManager`` queue, so they compose with breathing/emotions instead of
  fighting the 60 Hz control loop.
- Upstream ``BreathingMove`` hard-codes ``body_yaw=0.0`` (the body would snap
  back to center after every move); launch_patched patches its ``evaluate`` to
  return ``seeker.hold_yaw`` instead, so the body stays facing the person.

Env knobs:
- ``MEMOIRE_SEEK=0``            disable the scan behaviour (tracking stays on)
- ``MEMOIRE_HEAD_TRACKING=0``   don't auto-enable face tracking at startup
"""

from __future__ import annotations

import logging
import math
import threading
import time
from typing import Any, Sequence

import numpy as np

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised on the robot, stubbed in tests
    from reachy_mini.motion.move import Move
    from reachy_mini.utils import create_head_pose
except Exception:  # pragma: no cover
    class Move:  # type: ignore[no-redef]
        """Minimal stand-in so the module imports without the SDK (tests)."""

    def create_head_pose(*args: Any, **kwargs: Any) -> np.ndarray:  # type: ignore[no-redef]
        return np.eye(4, dtype=np.float64)


def _ease(t: float) -> float:
    """Cosine ease-in-out on [0, 1]."""
    t = min(max(t, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * t)


class ScanMove(Move):  # type: ignore[misc]
    """One scan leg: ease body yaw start->target, then hold so the detector can look.

    Head gets a small yaw lead in the sweep direction (stays well inside the
    65 deg head/body limit); antennas perk up slightly to read as "searching".
    """

    HEAD_LEAD_DEG = 18.0

    def __init__(self, start_yaw: float, target_yaw: float, speed_dps: float = 35.0, hold_s: float = 1.2):
        self.start_yaw = float(start_yaw)
        self.target_yaw = float(target_yaw)
        delta_deg = abs(math.degrees(self.target_yaw - self.start_yaw))
        self.travel_s = max(delta_deg / max(speed_dps, 1.0), 0.2)
        self.hold_s = float(hold_s)

    @property
    def duration(self) -> float:
        return self.travel_s + self.hold_s

    def evaluate(self, t: float) -> tuple[Any, Any, float]:
        if t < self.travel_s:
            frac = _ease(t / self.travel_s)
            yaw = self.start_yaw + (self.target_yaw - self.start_yaw) * frac
            direction = math.copysign(1.0, self.target_yaw - self.start_yaw)
            head_lead = math.radians(self.HEAD_LEAD_DEG) * direction * math.sin(math.pi * frac)
        else:
            yaw = self.target_yaw
            head_lead = 0.0
        head = create_head_pose(0, 0, 0, 0, 0, math.degrees(head_lead), degrees=True)
        antennas = np.array([-0.35, 0.35], dtype=np.float64)
        return (head, antennas, yaw)


def scan_targets(start_yaw: float, max_yaw: float = math.radians(150.0)) -> list[float]:
    """Widening left/right sweep targets from the current yaw, ending back at 0."""
    steps = [math.radians(d) for d in (60.0, 120.0)] + [max_yaw]
    targets: list[float] = []
    for step in steps:
        for side in (1.0, -1.0):
            yaw = side * step
            if abs(yaw - start_yaw) > math.radians(5.0):
                targets.append(yaw)
    targets.append(0.0)
    return targets


class FaceSeeker(threading.Thread):
    """Poll the daemon face tracker; sweep the body when everyone is lost."""

    def __init__(
        self,
        robot: Any,
        movement_manager: Any,
        auto_tracking: bool = True,
        seek_enabled: bool = True,
        lost_after_s: float = 8.0,
        poll_s: float = 0.5,
        cooldown_s: float = 90.0,
        speed_dps: float = 35.0,
        hold_s: float = 1.2,
    ):
        super().__init__(name="face-seeker", daemon=True)
        self.robot = robot
        self.manager = movement_manager
        self.auto_tracking = auto_tracking
        self.seek_enabled = seek_enabled
        self.lost_after_s = lost_after_s
        self.poll_s = poll_s
        self.cooldown_s = cooldown_s
        self.speed_dps = speed_dps
        self.hold_s = hold_s

        # Body yaw the breathing patch should hold (radians). Only this thread writes it.
        self.hold_yaw = 0.0

        self._stop = threading.Event()
        self._legs: list[float] = []
        self._scanning = False
        self._last_seen = time.monotonic()
        self._cooldown_until = 0.0

    def stop(self) -> None:
        self._stop.set()

    # -- helpers -----------------------------------------------------------

    def _tracking_on(self) -> bool:
        return bool(getattr(self.manager, "_head_tracking", False))

    def _queue_empty(self) -> bool:
        state = getattr(self.manager, "state", None)
        current = getattr(state, "current_move", None) if state is not None else None
        queue = getattr(self.manager, "move_queue", [])
        # Breathing is filler, not real work: scanning may interrupt it.
        breathing = current is not None and type(current).__name__ == "BreathingMove"
        return (current is None or breathing) and not queue

    def _abort_scan(self) -> None:
        self._scanning = False
        self._legs = []

    def _present_body_yaw(self) -> float:
        """Actual body yaw from the robot, falling back to the current anchor."""
        try:
            joints, _ = self.robot.get_current_joint_positions()
            return float(joints[0])
        except Exception:
            return self.hold_yaw

    # -- main loop ---------------------------------------------------------

    def run(self) -> None:
        if self.auto_tracking:
            try:
                self.manager.set_head_tracking(True)
                logger.info("FaceSeeker: head tracking auto-enabled")
            except Exception as e:
                logger.warning("FaceSeeker: could not enable head tracking: %s", e)

        while not self._stop.wait(self.poll_s):
            try:
                self._tick()
            except Exception as e:  # never kill the thread on a transient error
                logger.debug("FaceSeeker tick failed: %s", e)

    def _tick(self) -> None:
        now = time.monotonic()
        try:
            face = self.robot.get_tracked_face(wait=False)
            detected = bool(getattr(face, "detected", False))
        except Exception:
            return

        if detected:
            self._last_seen = now
            if self._scanning:
                # Let the current leg finish (its target is already hold_yaw);
                # just stop queueing further legs. The head tracker owns the face.
                self._abort_scan()
                logger.info("FaceSeeker: face found, scan stopped (body at %.0f deg)", math.degrees(self.hold_yaw))
            else:
                # Other moves (e.g. the upstream move_head tool, which resets
                # body_yaw to 0) may have moved the body; anchor where it
                # actually is so breathing doesn't snap it back to a stale yaw.
                self.hold_yaw = self._present_body_yaw()
            return

        if not self._scanning:
            # No face and no scan running: keep the anchor glued to reality so
            # breathing never snaps the body to a stale yaw.
            self.hold_yaw = self._present_body_yaw()

        if not (self.seek_enabled and self._tracking_on()):
            return

        if self._scanning:
            # Listening/real moves interrupt the scan; resume only via a new trigger.
            if not self._queue_empty():
                return
            if getattr(self.manager, "_is_listening", False):
                self._abort_scan()
                return
            if self._legs:
                target = self._legs.pop(0)
                self._queue_leg(target)
            else:
                self._scanning = False
                self._cooldown_until = now + self.cooldown_s
                logger.info("FaceSeeker: sweep done, nobody found; cooling down %.0fs", self.cooldown_s)
            return

        if now - self._last_seen < self.lost_after_s or now < self._cooldown_until:
            return
        if not self.manager.is_idle():
            return

        self.hold_yaw = self._present_body_yaw()
        self._legs = scan_targets(self.hold_yaw)
        self._scanning = True
        logger.info("FaceSeeker: nobody in frame for %.0fs, scanning", now - self._last_seen)
        target = self._legs.pop(0)
        self._queue_leg(target)

    def _queue_leg(self, target: float) -> None:
        leg = ScanMove(self.hold_yaw, target, speed_dps=self.speed_dps, hold_s=self.hold_s)
        self.hold_yaw = target
        self.manager.queue_move(leg)
