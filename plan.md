# Plan / decisions

## Approach

Upstream `reachy_mini_conversation_app` as a **dependency**, not a fork.
Everything plugs in through supported env vars:

| Env var | Value |
|---|---|
| `REACHY_MINI_EXTERNAL_PROFILES_DIRECTORY` | `profiles/` |
| `REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY` | `tools/` |
| `REACHY_MINI_CUSTOM_PROFILE` | `memoire` (locks profile without editing upstream `config.py`) |
| `REALTIME_TRANSCRIPTION_LANGUAGE` | `fr` |
| `MEMOIRE_DB_PATH` | `data/memoire.db` (our own var, read by the journal tools) |

Constraints from upstream loader (`core_tools.py`):
- External tool/profile names must NOT collide with built-ins (startup raises).
  Hence `journal_event`/`recall_journal`, not `remember`-style names.
- Each profile tool name resolves to `<tool_name>.py` in the external tools
  dir — one file per tool. Shared code lives in `_journal_db.py`
  (underscore-prefixed = ignored by the scanner), loaded by file path because
  external tool modules run outside any package.

## Phase 1 — minimal cloud version (NOW)

- [x] Repo scaffold, profile, journal tools, run.sh
- [ ] Smoke test in sim (`reachy-mini-daemon --sim` + `./run.sh --no-camera`)
- [ ] Real-robot test: memory (remember + journal + recall), camera describe,
      French latency/quality, greeting
- [ ] Tune profile wording from real transcripts
- [ ] Verify journal entries actually get written during a natural conversation
      (the model must call `journal_event` unprompted)

## Phase 2 — local inference POC

- Point `HF_REALTIME_CONNECTION_MODE=local` + `HF_REALTIME_WS_URL` at a
  self-hosted realtime (speech↔speech) endpoint on LAN.
- Candidate hosts: laptop RTX 8GB (tight) or a bigger box; needs an
  OpenAI-realtime-compatible server (e.g. open speech-to-speech stacks).
- Privacy is the motivation: no room audio leaving the house.

## Later (phase 3+)

- `people` table + face-recognition tool ("who is visiting") tied to camera.
- `reminders` table + proactive scheduler (APScheduler) injecting session
  messages — upstream is reactive-only; this is the real new code.
- Reminiscence: `stories` table, photo-backed conversations.

## Log

- 2026-08-15: repo created; phase-1 scaffold (profile + sqlite journal tools +
  launcher). Upstream cloned to `~/git/reachy_mini_conversation_app` for
  reference.
