"""Launch the conversation app with the memoire patches + hub.

Patches applied before the app starts:

1. WebRTC signalling-host override. Daemon 1.8.3 reports its hotspot IP
   (10.42.0.1) as ``wlan_ip`` even when joined to home wifi; the SDK then
   dials the signalling server on that unroutable address and times out
   (Field Log #5). ``REACHY_SIGNALLING_HOST`` forces the real robot address.

2. Hub wiring. Wraps ``LocalStream`` to (a) log final transcripts into the
   memoire DB and (b) start the hub server (caregiver dashboard + remote
   presence API) on ``MEMOIRE_HUB_PORT`` (default 7870) once the app is up.
   The hub is a separate port on purpose: it is the only thing a tunnel
   should ever expose — the upstream UI on :7860 has no auth.

3. Face seeking (needs daemon >= 1.9.0). Auto-enables the daemon face tracker
   and starts ``hub.seeker.FaceSeeker``: when nobody is in frame for a while,
   the body sweeps in widening yaw legs until a face is found, then anchors
   there. Upstream ``BreathingMove`` hard-codes ``body_yaw=0.0`` which would
   snap the body back to center between moves, so its ``evaluate`` is patched
   to hold the seeker's anchor yaw instead.
   Disable with ``MEMOIRE_SEEK=0`` (scan) / ``MEMOIRE_HEAD_TRACKING=0`` (tracking).
"""

import os
import sys
import logging
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

logger = logging.getLogger("memoire.launcher")

# ── patch 1: signalling host override ───────────────────────────────────────

from reachy_mini.media import media_manager as _mm  # noqa: E402

_real_init = _mm.MediaManager.__init__


def _patched_init(self, *args, **kwargs):
    override = os.getenv("REACHY_SIGNALLING_HOST")
    if override and "signalling_host" in kwargs:
        kwargs["signalling_host"] = override
    _real_init(self, *args, **kwargs)


_mm.MediaManager.__init__ = _patched_init

# ── patch 2: hub wiring ─────────────────────────────────────────────────────

from hub import db as hub_db  # noqa: E402
from hub.api import build_app  # noqa: E402
from hub.state import HubState  # noqa: E402

from reachy_mini_conversation_app import console as _console  # noqa: E402

_state = HubState()
_hub_started = threading.Event()


def _start_hub_once() -> None:
    if _hub_started.is_set():
        return
    _hub_started.set()
    import uvicorn

    port = int(os.getenv("MEMOIRE_HUB_PORT", "7870"))
    server = uvicorn.Server(
        uvicorn.Config(build_app(_state), host="0.0.0.0", port=port, log_level="warning")
    )
    threading.Thread(target=server.run, daemon=True, name="memoire-hub").start()
    print(f"Memoire hub on http://0.0.0.0:{port} (famille: /famille, suivi: /care)")


_LS = _console.LocalStream
_orig_ls_init = _LS.__init__
_orig_dispatch = _LS._dispatch_transcript


def _ls_init(self, *args, **kwargs):
    _orig_ls_init(self, *args, **kwargs)
    _state.attach(self)
    _start_hub_once()
    _start_seeker_once(self)


def _dispatch_transcript(self, role, text, final):
    _orig_dispatch(self, role, text, final)
    if not final:
        return
    try:
        hub_db.log_transcript(role, text, _state.run_id)
    except Exception as e:  # never let logging kill the conversation
        logger.warning("transcript logging failed: %s", e)


_LS.__init__ = _ls_init
_LS._dispatch_transcript = _dispatch_transcript

# ── patch 3: face seeking (tracking + body scan) ────────────────────────────

from hub.seeker import FaceSeeker  # noqa: E402
from reachy_mini_conversation_app import moves as _moves  # noqa: E402

_seeker: FaceSeeker | None = None
_seeker_started = threading.Event()

_orig_breathing_evaluate = _moves.BreathingMove.evaluate


def _breathing_evaluate(self, t):
    # Hold the seeker's anchor yaw instead of snapping the body back to 0.
    head, antennas, _ = _orig_breathing_evaluate(self, t)
    yaw = _seeker.hold_yaw if _seeker is not None else 0.0
    return (head, antennas, yaw)


_moves.BreathingMove.evaluate = _breathing_evaluate


def _start_seeker_once(stream) -> None:
    global _seeker
    if _seeker_started.is_set():
        return
    _seeker_started.set()
    deps = getattr(getattr(stream, "handler", None), "deps", None)
    robot = getattr(deps, "reachy_mini", None)
    manager = getattr(deps, "movement_manager", None)
    if robot is None or manager is None:
        logger.warning("face seeker not started: robot/movement_manager unavailable")
        return
    _seeker = FaceSeeker(
        robot,
        manager,
        auto_tracking=os.getenv("MEMOIRE_HEAD_TRACKING", "1") != "0",
        seek_enabled=os.getenv("MEMOIRE_SEEK", "1") != "0",
    )
    _seeker.start()
    print("Face seeker on (tracking + body scan; MEMOIRE_SEEK=0 to disable)")

# ── run upstream ────────────────────────────────────────────────────────────

from reachy_mini_conversation_app.main import main  # noqa: E402

main()
