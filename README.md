# Reachy Mémoire

A gentle memory companion for people living with Alzheimer's or memory loss,
running on [Reachy Mini](https://huggingface.co/docs/reachy_mini).

Reachy chats with them in French. It remembers what they tell it, keeps track of
what they need to do, and turns around to find them when they walk into the room.
Family members far away can use a phone page to see through its eyes and send
messages it reads out, or play their own recorded voice.

I built it for my grandparents. My grandfather has memory troubles and my
grandmother looks after him. In August 2026 the robot lived in their living
room. What happened there is how the "couple" profile and the turn-detection
settings below came about.

> **Status: working prototype, not a medical device.** It was built and run on a
> loaned Reachy Mini (July–September 2026). What was verified on the real robot
> and what wasn't is listed [below](#status).

## What it does

- **A calm companion.** Short, warm sentences. It never quizzes memory
  ("do you remember…?") and it gently helps with the day, date and place. It
  gives no medical advice.
- **Remembers for them.** Names of relatives, habits and preferences are kept
  across sessions. Depending on the profile, it also keeps a small care journal
  (visits, meals, mood…) or a list of tasks ("ask the bank for a cheque book").
- **Finds people.** When nobody has been in view for a few seconds, the body
  slowly turns to look around the room. When it sees a face, it stops and keeps
  looking at the person.
- **Connects the family** through a small web hub on the robot, protected by
  per-person access tokens:
  - **`/famille`**, for a relative's phone. Three big buttons: *see* (a camera
    snapshot, and Reachy says out loud who is looking), *write* (Reachy reads
    the message out word for word), *speak* (a recorded voice message played
    on the robot).
  - **`/care`**, for caregivers: conversations per day, mood, today's journal,
    and the questions he repeats most often over 30 days with a week-on-week
    trend. This is a factual answer to "what is he forgetting?", based only on
    his own words, with no model interpretation.

## Two profiles

| profile | for | behaviour |
|---|---|---|
| `memoire` (default) | one person with memory troubles | care-first: reorients gently, quietly keeps a care journal |
| `grandsparents` | a couple living at home | task-first: notes what they have to do, even when they're talking to each other, and asks **one** clarifying question at most. It keeps no journal: it's a companion, not a monitor |

Pick one with `REACHY_MINI_CUSTOM_PROFILE=grandsparents` (see
[configuration](docs/configuration.md)). Profiles are plain Markdown briefs in
[`profiles/`](profiles/). Writing one for another language or another household
means copying a folder.

## How it works

Mémoire is **not a fork**. It runs Pollen's
[`reachy_mini_conversation_app`](https://github.com/pollen-robotics/reachy_mini_conversation_app)
as a dependency and plugs into it:

```
reachy_mini_conversation_app  (speech ↔ speech, HF realtime backend, camera, moves)
 ├── profiles/            ← our profiles (supported: external profiles dir)
 ├── tools/               ← our tools: journal + tasks, SQLite (supported: external tools dir)
 └── scripts/launch.py    ← three small hooks upstream has no option for yet:
       1. hub      – web server on :7870 + transcript logging
       2. seeker   – face tracking + body scan when nobody is in view
       3. VAD      – turn detection tuned for a room where people talk to each other
hub/                      ← the family page, care dashboard, speech, face seeker
```

Each hook is small, isolated and can be switched off. Each one maps to an
upstream change that would let us delete it: see [docs/upstream.md](docs/upstream.md).

## Quick start

**On the robot (the real deployment: power on, and it runs).** From a computer
on the same network:

```bash
ssh pollen@reachy-mini.local "HF_TOKEN=hf_... ROBOT_SUDO_PASS=root bash -s" \
  < scripts/install_on_robot.sh
```

That installs Mémoire next to the robot's own software, never replacing it, as
a service that starts at boot. About 70 s after power-on, Reachy greets you.
Full guide: [docs/install-on-robot.md](docs/install-on-robot.md).

**From a laptop (development).** The robot must be on the same network, or use
the simulator with `reachy-mini-daemon --sim`:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv git+https://github.com/pollen-robotics/reachy_mini_conversation_app edge-tts
hf auth login                      # or export HF_TOKEN=...
./run.sh                           # add --ui for the upstream web UI on :7860
```

`ffmpeg` must be installed. Then create a link for a family member:

```bash
.venv/bin/python scripts/make_tokens.py mamie    # prints the /famille and /care URLs
```

## Status

| | verified on the real robot | how |
|---|---|---|
| Conversation, French greeting, camera, tools loading | ✅ 17 Aug 2026 | bring-up |
| Hub: camera snapshot, "say" pipeline to the speaker, transcript logging | ✅ 23 Aug 2026 | from a laptop after a reboot |
| Face seeking: sweep, face found, body anchored | ✅ 19 Aug 2026 | live |
| Runs at boot with no laptop (greeting at +68 s) | ✅ 23 Aug 2026 | real reboot |
| `grandsparents` profile + turn-detection tuning | ✅ 30 Aug 2026 | at my grandparents' home |
| Hearing hub messages from the speaker in the room | ⬜ | pipeline verified, sound not checked by ear |
| Recording a voice message from a phone | ⬜ | needs HTTPS (tunnel), never tested end to end |
| Access from outside the home (`scripts/expose.sh`, Tailscale Funnel) | ⬜ | written, never tested |
| Model keeps the journal unprompted in `memoire` profile | ⬜ | not observed in a long conversation |

The hub and the face seeker have tests that need no robot and no network:

```bash
uv run --no-project --with fastapi --with httpx --with python-multipart python tests/test_hub.py
uv run --no-project --with numpy python tests/test_seeker.py
```

## Privacy

This app listens in someone's home and holds sensitive data about a vulnerable
person. Read [docs/privacy.md](docs/privacy.md) before installing it for
someone else. In short:

- speech goes to the Hugging Face realtime backend;
- transcripts, journal and tasks stay on the robot in SQLite;
- the camera is only viewed remotely on request, and Reachy says out loud who is
  looking;
- only the token-protected hub port (7870) may ever be exposed.

## Documentation

- [Install on the robot](docs/install-on-robot.md): service, day-to-day use,
  putting the robot on a new Wi-Fi network without a screen, demo checklist
- [Family hub](docs/family-hub.md): pages, access tokens, remote access
- [Configuration](docs/configuration.md): every environment variable
- [Troubleshooting](docs/troubleshooting.md): known robot/SDK pitfalls, where
  logs and data live
- [Privacy](docs/privacy.md)
- [Upstream changes](docs/upstream.md): what would let us delete the hooks
- [Design notes](docs/design-notes.md): decisions and dated development log

## Roadmap

- Package as a Reachy Mini app-store app.
- English profile, translatable hub pages.
- Proactive reminders ("today you have…"). Upstream is reactive-only.
- Local inference on the home network, so no audio leaves the house.
- Live video and two-way calls on `/famille`.

## Credits and licence

By Corentin Bel, on a Reachy Mini lent by
[Pollen Robotics](https://www.pollen-robotics.com/). Built on
`reachy_mini_conversation_app` and the `reachy_mini` SDK (Pollen Robotics /
Hugging Face). Licensed under [Apache 2.0](LICENSE).
