# Upstream changes that would simplify Mémoire

Mémoire uses the conversation app's supported extension points (external
profiles and tools) for everything they cover. Three features need more than
that. For now they are small hooks in [`scripts/launch.py`](../scripts/launch.py).
Each would disappear with one upstream option, and each is also useful beyond
this app.

| hook in `launch.py` | why | upstream change that removes it |
|---|---|---|
| **1. Hub wiring**: wraps `LocalStream.__init__` and `LocalStream._dispatch_transcript` | start a companion web server with access to the live session, and log every final transcript turn | a small public hook API: `on_session_ready(stream)`, `on_transcript(role, text, final)`. Speaking a text verbatim already works through the SDK (`media.play_sound`) |
| **2. Face seeking**: patches `BreathingMove.evaluate` | the breathing idle move sets `body_yaw=0` on every frame, so after the body turns toward a person it snaps back to the centre | breathing keeps the current body yaw (plus, optionally, a built-in "look for people" idle behaviour) |
| **3. Turn detection**: patches `HuggingFaceRealtimeHandler._get_session_config` | `ServerVad(type="server_vad", interrupt_response=True)` is hardcoded, and its defaults break down when several people talk in the room | expose `threshold`, `silence_duration_ms`, `prefix_padding_ms`, `interrupt_response` in the profile or as env vars |

Related finding, reported separately: the `move_head` tool resets `body_yaw` to
0, and starts its interpolation from `current_antennas[0]` (the left antenna
angle) instead of the body yaw.

Once these land, `scripts/launch.py` shrinks to starting the hub. The journal
and task tools could also ship as a tool Space (MCP), leaving Mémoire as
profiles + tools + hub.
