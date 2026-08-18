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

# ── run upstream ────────────────────────────────────────────────────────────

from reachy_mini_conversation_app.main import main  # noqa: E402

main()
