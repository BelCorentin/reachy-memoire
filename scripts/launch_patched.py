"""Launch the conversation app with a WebRTC signalling-host override.

Daemon 1.8.3 reports its hotspot IP (10.42.0.1) as ``wlan_ip`` even when it is
joined to a home wifi network; the SDK then dials the WebRTC signalling server
on that unroutable address and times out (Field Log #5). Until the daemon is
updated, ``REACHY_SIGNALLING_HOST`` forces the real robot address.
"""

import os

from reachy_mini.media import media_manager as _mm

_real_init = _mm.MediaManager.__init__


def _patched_init(self, *args, **kwargs):
    override = os.getenv("REACHY_SIGNALLING_HOST")
    if override and "signalling_host" in kwargs:
        kwargs["signalling_host"] = override
    _real_init(self, *args, **kwargs)


_mm.MediaManager.__init__ = _patched_init

from reachy_mini_conversation_app.main import main  # noqa: E402

main()
