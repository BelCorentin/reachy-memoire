# Configuration

Everything is set with environment variables: export them before `./run.sh`,
or on the robot put them in `/etc/reachy-memoire.env` and run
`sudo systemctl restart reachy-memoire`.

## Mémoire

| variable | default | what |
|---|---|---|
| `REACHY_MINI_CUSTOM_PROFILE` | `memoire` | `memoire` (one person, care journal) or `grandsparents` (couple, tasks) |
| `MEMOIRE_DB_PATH` | `data/memoire.db` | SQLite file: journal, tasks, transcripts |
| `MEMOIRE_HUB_PORT` | `7870` | family hub port |
| `MEMOIRE_TTS_VOICE` | `fr-FR-DeniseNeural` | edge-tts voice for messages read on the robot |
| `MEMOIRE_FFMPEG` | `ffmpeg` | ffmpeg binary |
| `MEMOIRE_HEAD_TRACKING` | `1` | `0` = don't turn on face tracking at startup |
| `MEMOIRE_SEEK` | `1` | `0` = don't turn the body to look for people |
| `MEMOIRE_DAEMON_WAIT` | `180` | seconds the boot service waits for the robot daemon |
| `REACHY_HOST` | `reachy-mini.local` (`127.0.0.1` on the robot) | daemon address used by the startup checks |

## Turn detection

The conversation app sends speech to the model when it hears a turn end. Its
defaults are tuned for **one person speaking to the robot**. In a living room
where two people talk to each other, they made Reachy cut its own reply every
1–2 seconds. These settings fix that, and they can be retuned in the room with
no redeploy:

| variable | Mémoire default | upstream default | effect |
|---|---|---|---|
| `MEMOIRE_VAD_THRESHOLD` | `0.7` | 0.5 | higher = needs louder or closer speech to start a turn |
| `MEMOIRE_VAD_SILENCE_MS` | `1200` | 500 | how long a pause must be to count as the end of a turn |
| `MEMOIRE_VAD_PREFIX_MS` | `300` | 300 | audio kept before speech starts |
| `MEMOIRE_VAD_INTERRUPT` | `0` | on | `1` = any speech cancels Reachy's reply in progress |

At startup the log shows `VAD: threshold=0.7 silence=1200ms interrupt=False`.
If it still interrupts itself, raise the threshold. If it feels slow to answer,
lower the silence.

## Set by `run.sh` for the conversation app

`REACHY_MINI_EXTERNAL_PROFILES_DIRECTORY=profiles/`,
`REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY=tools/`, `AUTOLOAD_EXTERNAL_TOOLS=1`,
`REALTIME_TRANSCRIPTION_LANGUAGE=fr`. All other upstream variables work as
documented in `reachy_mini_conversation_app`. That includes
`HF_REALTIME_CONNECTION_MODE=local` + `HF_REALTIME_WS_URL` to use your own
realtime server.

## Secrets

`HF_TOKEN`: export it, use `hf auth login`, or on the robot keep it in
`/etc/reachy-memoire.env`. Never commit it.

Note: the Hugging Face realtime backend currently also accepts sessions
**without** a token. So a missing token doesn't show up at install time. It
shows up later as a quota or rate-limit error. Check that the file actually
contains `HF_TOKEN=`.
