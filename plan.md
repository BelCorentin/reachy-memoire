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

## Hub — caregiver dashboard + family remote (2026-08-18)

In-process FastAPI on **:7870** (own port on purpose: it is the ONLY thing a
tunnel may expose — the upstream UI on :7860 has no auth). Wired by
`scripts/launch_patched.py` wrapping `LocalStream`:

- `__init__` wrap → captures the live stream (handler + robot refs) and starts
  the hub uvicorn thread once.
- `_dispatch_transcript` wrap → logs every `final=True` turn into
  `transcript` table in `memoire.db` (WAL mode; shared with journal tools).

Key upstream facts this relies on:
- `handler.say(text)` = **injected turn**, model voices it — not verbatim TTS
  (`conversation_handler.py`). Good enough for "mamie fait parler Reachy";
  verbatim fallback would be edge-tts WAV into the audio queue.
- `LocalStream.clear_audio_queue()` = barge-in, mirrored from upstream's
  `conversation.say` RPC.
- Cross-loop: hub server has its own event loop; `HubState.say` uses
  `run_coroutine_threadsafe` onto `stream._asyncio_loop` when set.

Routes (all token-auth except `/health`): `/famille` (grandma PWA: snapshot
polling 2.5s + say + canned phrases), `/care` (dashboard: turns/day, mood,
journal timeline, repeated-utterance clusters), `/api/say|snapshot|status|
phrases|view/start|care/summary`. Auth: `data/hub_tokens.json` via
`scripts/make_tokens.py` (Bearer / `?t=` / cookie); per-person rate limits
(say 1/5s, snapshot 1/s); say capped 400 chars; view-start announces "X
regarde" max 1/min.

Repetition detector = the "what is he forgetting" signal: normalize (lower,
strip accents/punct), greedy fuzzy clustering (difflib ratio ≥ .8), report
clusters ≥3× over 30 d with this-week vs prev-week trend. Stdlib only.

Remote access: `scripts/expose.sh` → Tailscale Funnel of :7870 (preferred,
stable URL) or `--cloudflared` quick tunnel. **Neither installed locally yet —
tunnel path untested.** Never funnel :7860.

### Verbatim speech (2026-08-18, same day)

`hub/speech.py`: edge-tts → mp3 → ffmpeg → mono 44.1k WAV, cached by
voice+text hash; voice-message uploads (webm/mp4/ogg from MediaRecorder)
converted the same way. Playback = SDK `media.play_sound(file)` which uploads
to the daemon and POSTs `/api/media/play_sound` — **independent of the
realtime session** (works while the model is idle; `/api/say` tts mode and
`/api/voice` both work with no session up, tested). Barge-in still clears the
assistant audio queue first.

- `/api/say` default `mode="tts"` = verbatim; `mode="ai"` = old injected turn.
- `/api/voice` = grandma's REAL voice on the robot — chosen over voice
  cloning: simpler, authentic, no training data needed. True cloning (XTTS-v2
  fine-tuned on her samples, local) is a phase-2 candidate if TTS-voice
  messages feel too robotic.
- Both prefixed by a TTS "Message de X." so grandpa knows who speaks.
- getUserMedia requires HTTPS → recording works through the funnel or
  localhost only; plain `http://<lan-ip>` shows mic-refused.
- Caveat not yet measured live: robot mic hears the played message — the
  model may respond to it. If annoying, mute mic during playback
  (`LocalStream._mic_muted`) — left for the live test.

- [x] M1 transcript logging (tested: unit)
- [x] M2 hub routes + dashboard v1 + famille page (tested: 26-check suite,
      stubbed robot/handler — `tests/test_hub.py`)
- [x] M3 auth/tokens/expose script (funnel itself untested, no tailscale here)
- [x] M4 repetition detector + canned phrases (`data/phrases.json`, seeded)
- [ ] Live test with robot: transcript rows appear during real conversation,
      snapshot from phone, say from phone, view announcement
- [ ] Install tailscale + funnel end-to-end from a phone on 4G
- [ ] Later: live WebRTC video instead of snapshot polling

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
