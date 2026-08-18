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
- **Orientation**: time/date tool for "what day is it?".

Inference is Hugging Face's cloud realtime backend (speech↔speech). Phase 2 =
local inference POC via `HF_REALTIME_CONNECTION_MODE=local` +
`HF_REALTIME_WS_URL` pointing at a self-hosted realtime endpoint.

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

## Operations (day-to-day, no desktop app needed)

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
- SDK 1.10.0rc5 vs daemon 1.8.3 version-mismatch warning is benign so far;
  the daemon offers a 1.9.0 self-update (`GET /update/available`) if it ever
  isn't.

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
