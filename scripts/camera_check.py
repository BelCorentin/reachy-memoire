"""Standalone check: connect to the robot, grab one camera frame, save it.

Usage: .venv/bin/python scripts/camera_check.py [out.jpg]
Needs REACHY_SIGNALLING_HOST when the daemon still reports its hotspot IP
(daemon 1.8.3 bug, see Field Log #5) — run via run-env or export it.
"""

import os
import sys
import time

from reachy_mini.media import media_manager as _mm

_real_init = _mm.MediaManager.__init__


def _patched_init(self, *args, **kwargs):
    override = os.getenv("REACHY_SIGNALLING_HOST")
    if override and "signalling_host" in kwargs:
        kwargs["signalling_host"] = override
    _real_init(self, *args, **kwargs)


_mm.MediaManager.__init__ = _patched_init

from reachy_mini import ReachyMini  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else "camera_check.jpg"
robot = ReachyMini(connection_mode="network", timeout=30)
deadline = time.time() + 15
jpeg = None
while time.time() < deadline:
    try:
        jpeg = robot.media.get_frame_jpeg()
    except Exception:
        jpeg = None
    if jpeg:
        break
    time.sleep(0.5)

if not jpeg:
    print("FAIL: no frame within 15s")
    sys.exit(1)

with open(out, "wb") as f:
    f.write(jpeg)
print(f"OK: {len(jpeg)} bytes -> {out}")
