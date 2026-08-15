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

## Data & backup

- Journal DB: `data/memoire.db` (gitignored). The loaner robot gets wiped —
  back it up: `scp pollen@reachy-mini.local:.../data/memoire.db backups/`.
- Facts store: upstream `memory.v1.json` in
  `~/.local/share/reachy_mini_conversation_app/`.

## Roadmap

See `plan.md`.
