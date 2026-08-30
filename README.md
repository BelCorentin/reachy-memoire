# reachy-memoire

Memory-companion app for Reachy Mini, aimed at people with Alzheimer's / memory
troubles. Built **on top of** Pollen's
[`reachy_mini_conversation_app`](https://github.com/pollen-robotics/reachy_mini_conversation_app)
(installed as a dependency, not forked): a custom French care profile + SQLite
journal tools plugged in via the app's external profile/tool mechanism.

## What it does (phase 1 — cloud)

- **French companion profile** (`profiles/memoire/`): calm, short sentences,
  never quizzes, gently reorients, no medical advice. Locked via
  `REACHY_MINI_CUSTOM_PROFILE`.
- **Long-term facts**: upstream `remember`/`forget` tools (names of relatives,
  habits, preferences) — injected into every session prompt.
- **Care journal** (`tools/journal_event.py` + `tools/recall_journal.py`,
  shared SQLite layer in `tools/_journal_db.py`): `journal_event` silently logs notable
  moments (visits, meals, medication, mood, activities) into SQLite
  (`data/memoire.db`); `recall_journal` answers "what did I do today?",
  "who visited?", filtered by day/keyword.
- **Camera + head tracking**: describe the real scene on request, look at the
  person while talking.
- **Face seeking** (`hub/seeker.py`, needs robot daemon ≥ 1.9.0): face tracking
  is auto-enabled at startup, and when nobody has been in frame for ~8 s the
  body slowly sweeps in widening yaw legs (±60° → ±120° → ±150°) until the
  tracker finds a face, then anchors there — so the robot turns around to look
  for people instead of staring at a wall. After a full empty sweep it recenters
  and cools down for 90 s. Disable the sweep with `MEMOIRE_SEEK=0`, or startup
  tracking entirely with `MEMOIRE_HEAD_TRACKING=0`.
- **Orientation**: time/date tool for "what day is it?".

Inference is Hugging Face's cloud realtime backend (speech↔speech). Phase 2 =
local inference POC via `HF_REALTIME_CONNECTION_MODE=local` +
`HF_REALTIME_WS_URL` pointing at a self-hosted realtime endpoint.

## Profiles

Two, selected with `REACHY_MINI_CUSTOM_PROFILE` (default `memoire`):

| profile | for | shape |
|---|---|---|
| `memoire` | one person with memory troubles | care-first: never quizzes, gently reorients, silently logs a care journal |
| `grandsparents` | a couple, living independently | task-first: captures what they have to do, asks the ONE question that makes a note usable, reads the list back |

`grandsparents` adds `add_task` / `list_tasks` / `complete_task` (a `tasks`
table in the same `data/memoire.db`) and drops `journal_event` from its tool
list — it is a companion, not a monitor. Its brief is deliberate about the
clarifying question: exactly one at a time, never twice for the same fact, and
if the answer doesn't come the task is saved vague rather than pursued. An
interrogation is worse than an imperfect note.

Switch it on the robot by editing `/etc/reachy-memoire.env`:

```bash
REACHY_MINI_CUSTOM_PROFILE=grandsparents
```

then `sudo systemctl restart reachy-memoire`. Locally, just export it before
`./run.sh`.

## Turn detection (barge-in)

Upstream builds `ServerVad(type="server_vad", interrupt_response=True)` and
sets nothing else, so the server defaults apply — `threshold 0.5`,
`silence_duration_ms 500`. With **two people talking to each other** that is far
too eager: observed 2026-08-30, the reply was cancelled every 1–2 s and the user
transcript grew into one runaway sentence. `launch_patched.py` patch 4
overrides it; all four knobs are env vars, so they can be retuned in the room
and the service restarted, with no redeploy:

| env | default here | upstream/server default |
|---|---|---|
| `MEMOIRE_VAD_THRESHOLD` | `0.7` | 0.5 |
| `MEMOIRE_VAD_SILENCE_MS` | `1200` | 500 |
| `MEMOIRE_VAD_PREFIX_MS` | `300` | 300 |
| `MEMOIRE_VAD_INTERRUPT` | `0` (off) | on |

Startup logs the applied values: `VAD: threshold=0.7 silence=1200ms interrupt=False`.
Still barging in → raise the threshold. Feels sluggish / lets you ramble →
lower `MEMOIRE_VAD_SILENCE_MS`.

## Wifi: getting the robot onto a new network, headless

The robot falls back to its own AP (`reachy-mini-ap`, password `reachy-mini`,
`10.42.0.1`) whenever no known network is in range — **silently**: from the
laptop it looks exactly like a robot that is off. A wifi scan showing
`reachy-mini-ap` is the tell.

The documented way back is the dashboard in a browser. The headless way is
`POST /wifi/connect` on the daemon, wrapped here:

```bash
HOTSPOT_PSK='...' ./scripts/provision_hotspot.sh 'My Network'
```

It joins the AP, pushes the credentials, rejoins your network, then sweeps for
the robot and prints `/wifi/status` + `:7870/health`. The machine running it is
**offline for the middle of the round trip**, which is why it logs to
`logs/provision-*.log` rather than expecting anyone to watch it. Arg 1 must be
both the SSID to teach the robot and the name of the saved NetworkManager
profile to return to.

## The hub (family remote + caregiver dashboard)

A second web server runs **inside the same process** on port **7870** (started
by `run.sh` automatically). It is deliberately separate from the upstream UI
on :7860: the hub is token-authenticated and is the only thing you may ever
expose to the internet.

- **`/famille`** — phone page for a remote relative, designed senior-first
  (three huge buttons, big type, one thing at a time):
  - **🎙️ voice message**: tap, speak, tap — her *actual voice* plays on the
    robot's speaker (MediaRecorder upload → ffmpeg → WAV → daemon
    `play_sound`), prefixed by a short "Message de X." announcement.
    Needs HTTPS (funnel) or localhost — browsers block the mic on plain HTTP.
  - **👁 watch**: camera snapshot every 2.5 s; Reachy announces who is watching.
  - **✏️ written message**: spoken **verbatim** on the robot speaker via
    edge-tts (default voice `fr-FR-DeniseNeural`, override `MEMOIRE_TTS_VOICE`;
    synth cached in `data/tts_cache/`). `{"mode": "ai"}` on `/api/say` keeps
    the old behavior (injected turn, the model voices it in its own voice).
  Add-to-homescreen on iPhone/Android → feels like an app.
- **`/care`** — caregiver dashboard: conversation volume per day, mood entries,
  the day's care journal, and **repeated questions/phrases over 30 days with a
  week-over-week trend** — the honest "what is he forgetting" signal (fuzzy
  clustering of his own words, no model opinions).
- **Transcript logging** — every final user/assistant turn is stored in
  `data/memoire.db` (`transcript` table). This is the analytics substrate;
  it starts accumulating from the first run.

### Access control

```bash
.venv/bin/python scripts/make_tokens.py mamie celine   # prints share URLs
```

Tokens live in `data/hub_tokens.json` (gitignored). Opening
`/famille?t=<token>` once stores it as a cookie on the phone. Per-person rate
limits on say/snapshot/voice; `/api/say` capped at 400 chars, voice uploads
at 8 MB.

### Remote access (family outside the LAN)

```bash
./scripts/expose.sh                 # Tailscale Funnel of :7870 (preferred)
./scripts/expose.sh --cloudflared   # ephemeral fallback URL
```

Then regenerate share links with `--base-url <public url>`. **Never tunnel
:7860** — the upstream UI has no auth. (Funnel path not yet live-tested;
tailscale isn't installed on this laptop.)

## Setup

1. Install the upstream app (SDK first, per its README):

   ```bash
   uv venv --python python3.12 .venv && source .venv/bin/activate
   uv pip install git+https://github.com/pollen-robotics/reachy_mini_conversation_app edge-tts
   ```

   `ffmpeg` must be on PATH (hub TTS + voice-message conversion).

2. Authenticate: `hf auth login` (or `export HF_TOKEN=...`).

3. Run (robot daemon must be up; use `reachy-mini-daemon --sim` for desk dev):

   ```bash
   ./run.sh --ui          # Gradio UI on :7860
   ./run.sh --no-camera   # audio-only
   ```

## Robot-side install (standalone: power on → memoire runs)

This is the deployment mode that matters outside the lab — a phone hotspot and
a power cable, no laptop anywhere. The app runs **on the Raspberry Pi inside
the robot**, as a systemd service, alongside (never replacing)
`reachy-mini-daemon.service`.

```bash
# one command, from the laptop, idempotent — re-run it to update the robot
ssh pollen@reachy-mini.local \
  "HF_TOKEN=$(cat ~/.cache/huggingface/token) ROBOT_SUDO_PASS=root bash -s" \
  < scripts/install_on_robot.sh

# runtime state that is NOT in git (hub tokens, canned phrases, the journal)
rsync -av data/hub_tokens.json data/phrases.json data/memoire.db \
      pollen@reachy-mini.local:/home/pollen/reachy-memoire/data/
```

After a wipe there is no local clone to pipe from, so pull the script straight
from GitHub instead:

```bash
curl -fsSL https://raw.githubusercontent.com/BelCorentin/reachy-memoire/master/scripts/install_on_robot.sh \
  | ssh pollen@reachy-mini.local "HF_TOKEN=hf_... ROBOT_SUDO_PASS=root bash -s"
```

What it does: `apt install ffmpeg` · clone to `/home/pollen/reachy-memoire` ·
`uv venv --python 3.12` + install the upstream app and `edge-tts` ·
write `/etc/reachy-memoire.env` · install and enable
`reachy-memoire.service` · wait for `:7870/health`.

**Secrets never go in git.** `HF_TOKEN` lives in `/etc/reachy-memoire.env`
(root-owned, 0600), referenced by the unit's `EnvironmentFile`. Without a
token the service still starts and the hub answers, but the realtime session
cannot open. Rotate it with:

```bash
ssh pollen@reachy-mini.local "echo 'HF_TOKEN=hf_...' | sudo tee /etc/reachy-memoire.env" \
  && ssh pollen@reachy-mini.local "sudo systemctl restart reachy-memoire"
```

### The unit

`scripts/reachy-memoire.service` runs `run.sh` as `pollen` with
`REACHY_HOST=REACHY_SIGNALLING_HOST=127.0.0.1`. On the robot the daemon is on
loopback, which sidesteps the `wlan_ip` signalling bug entirely and works even
before wifi associates.

`After=reachy-mini-daemon.service` only orders unit *start* — the daemon's REST
API answers tens of seconds later, and it always boots with motors disabled.
So `ExecStartPre=scripts/wait_for_daemon.sh` polls `/api/daemon/status` until
`state: running` (180 s budget), then does the media-acquire and motors-enable
preflights. `Restart=on-failure`, `RestartSec=10`.

Note the app's own inactivity timeout is 24 h
(`REACHY_MINI_APP_TIMEOUT_MINUTES`); when it fires, the app exits *cleanly*, so
`on-failure` deliberately does not restart it — same for the voice
"endors-toi" tool. `sudo systemctl restart reachy-memoire` wakes it back up.

### Day-to-day on the robot

```bash
sudo systemctl status  reachy-memoire     # is it up
journalctl -u reachy-memoire -f           # live logs (also logs/latest.log)
sudo systemctl restart reachy-memoire     # after changing the env file
curl -s http://reachy-mini.local:7870/health   # from any LAN machine
```

Family/care links are the same as before, on the robot's own address:
`http://reachy-mini.local:7870/famille?t=<token>`. Regenerate them with
`scripts/make_tokens.py --base-url http://reachy-mini.local:7870`.
Only :7870 may ever be exposed beyond the LAN — :7860 has no auth, and the
service does not start the Gradio UI at all.

### Demo-day checklist (robot only, phone hotspot)

1. Turn the hotspot on **first**, then power the robot — it auto-joins any
   network already in `curl http://reachy-mini.local:8000/wifi/status`
   (`known_networks`). A new hotspot has to be added once from the robot's
   own AP (10.42.0.1) or the dashboard on :8000.
2. Wait ~70 s. Measured on a cold boot: daemon REST ready at +18 s, service
   active at +34 s, realtime session open and greeting spoken at +68 s.
3. From a phone on the same hotspot: `http://reachy-mini.local:7870/health`
   should return `{"ok":true,"session":true}`. `session:false` means the
   HF realtime connection did not open — check `HF_TOKEN` and internet.
4. The robot needs internet the whole time: inference is HF cloud, and the
   hub's TTS calls Microsoft edge-tts. No internet = no speech at all.

## Operations (laptop-driven, no desktop app needed)

The Pollen desktop app is **only** a convenience for wifi provisioning and app
management — nothing here depends on it. Everything talks straight to the
robot's daemon (REST + WebSocket on port 8000, autostarted at boot by
`reachy-mini-daemon.service`).

**Every startup is just:**

1. Power the robot on. It auto-joins any known wifi (list at
   `http://<robot>:8000/wifi/status`); if none is reachable it falls back to
   its own hotspot (10.42.0.x) where you provision wifi once via the built-in
   dashboard on port 8000 — no desktop app required.
2. `./run.sh --ui` on the laptop. The script resolves the robot, wakes the
   daemon's media stack, applies the signalling workaround, and starts the
   conversation app (web UI + transcript at http://localhost:7860).

Wifi is required only for laptop↔robot transport and the HF cloud backend —
the robot has no other network dependency at runtime.

**Verified working (2026-08-17):** robot connection, WebRTC bidirectional
audio, camera (`scripts/camera_check.py` grabs a JPEG frame), profile +
journal tools loading, realtime session + French greeting.

### Known gotchas

- Daemon 1.8.3 reports its **hotspot IP** (10.42.0.1) as `wlan_ip` even when
  on home wifi → the SDK dials WebRTC signalling on an unroutable address and
  times out. `run.sh` works around it via `REACHY_SIGNALLING_HOST` +
  `scripts/launch_patched.py`.
- If WebRTC still times out, check the signalling server:
  `curl -X POST http://<robot>:8000/api/media/acquire` then verify port 8443
  is open.
- **Robot daemon boots with motors disabled** (`motor_control_mode: disabled`,
  no error anywhere) — the head just doesn't move. Enable with
  `curl -X POST http://<robot>:8000/api/motors/set_mode/enabled`.
- **Face tracking needs daemon ≥ 1.9.0.** On 1.8.3 the `SetHeadTrackingCmd`
  is silently ignored (`get_tracked_face()` returns `detected=False, ts=None`
  forever, no version error). Robot updated to 1.9.0 on 2026-08-18 via
  `curl -X POST http://<robot>:8000/update/start` — note the update routes are
  **unprefixed** (`/update/...`, not `/api/update/...`). Motors come back
  disabled after the update (see above).
- **After a daemon self-update, restart the daemon** (`POST /api/daemon/restart`).
  The post-update state can be wedged: every command is accepted (goto returns a
  uuid, `nb_error: 0`, no log errors) but nothing physically moves — encoders
  frozen, `/api/move/running` always empty, `write_dt ~0.07ms` in
  `control_loop_stats` (healthy is ~0.4ms). Restart + re-enable motors fixes it.
- **"Command accepted" ≠ "robot moved".** The only ground truth is reading
  encoders back (`/api/state/present_head_pose` before/after, or
  `get_current_joint_positions()`). SDK calls returning cleanly proves nothing.
- SDK 1.10.0rc5 vs daemon 1.9.0 version-mismatch warning is benign so far
  (motion, tracking commands, and `play_sound` all verified).

## Where things are logged / stored

| What | Where |
|---|---|
| App run logs (full console output) | `logs/run-<timestamp>.log` (+ `logs/latest.log` symlink), gitignored |
| Care journal (visits, meals, meds, mood) | `data/memoire.db` (SQLite), gitignored |
| Conversation transcripts (final turns) | `data/memoire.db`, `transcript` table |
| Hub access tokens / canned phrases | `data/hub_tokens.json` / `data/phrases.json`, gitignored |
| TTS cache / voice messages | `data/tts_cache/` / `data/voicemail/`, gitignored |
| Long-term facts (`remember` tool) | `~/.local/share/reachy_mini_conversation_app/memory.v1.json` |
| Robot-side daemon logs | on the robot: `journalctl -u reachy-mini-daemon` (ssh `pollen@reachy-mini.local`) |

The loaner robot gets wiped at loan end — nothing irreplaceable lives on it;
everything above is laptop-side except the daemon logs.

## Roadmap

See `plan.md`.
