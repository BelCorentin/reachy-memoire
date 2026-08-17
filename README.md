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

## Setup

1. Install the upstream app (SDK first, per its README):

   ```bash
   uv venv --python python3.12 .venv && source .venv/bin/activate
   uv pip install git+https://github.com/pollen-robotics/reachy_mini_conversation_app
   ```

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
| Long-term facts (`remember` tool) | `~/.local/share/reachy_mini_conversation_app/memory.v1.json` |
| Robot-side daemon logs | on the robot: `journalctl -u reachy-mini-daemon` (ssh `pollen@reachy-mini.local`) |

The loaner robot gets wiped at loan end — nothing irreplaceable lives on it;
everything above is laptop-side except the daemon logs.

## Roadmap

See `plan.md`.
