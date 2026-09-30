# Family hub

A small web server runs inside the Mémoire process on port **7870**. It is
separate from the conversation app's own web UI (port 7860) on purpose: the
hub requires a per-person token, and the upstream UI has no authentication.
**Only port 7870 may ever be exposed outside the home.**

## `/famille`: for a relative's phone

It's designed for an elderly person: three huge buttons, large text, one thing
at a time. Adding it to the phone's home screen makes it feel like an app.

- **👁 See**: a camera snapshot every 2.5 s. When someone starts watching,
  Reachy says so out loud ("Mamie nous regarde…"), at most once a minute.
  Nobody can watch silently.
- **✏️ Write**: Reachy reads the message out **word for word** (edge-tts,
  default voice `fr-FR-DeniseNeural`), after announcing "Message de Mamie."
  Playback goes straight to the robot's speaker, so it works even while the AI
  conversation is idle.
- **🎙️ Speak**: record a voice message, and the relative's **real voice** plays
  on the robot. We chose this over voice cloning: it's simpler and more honest.
  Browsers only allow the microphone over HTTPS, so this works through the
  remote-access tunnel or on `localhost`, not on a plain `http://` LAN address.

Canned phrases for one-tap messages live in `data/phrases.json`.

## `/care`: for caregivers

- conversations per day;
- mood entries and today's care journal (`memoire` profile);
- **repeated questions over 30 days**, with the trend this week against last
  week. His own sentences are grouped by fuzzy matching. The dashboard shows
  what he says, not a model's opinion of it.

## Access

```bash
.venv/bin/python scripts/make_tokens.py mamie celine   # create/rotate, prints the links
.venv/bin/python scripts/make_tokens.py --list
.venv/bin/python scripts/make_tokens.py --remove celine
```

Tokens live in `data/hub_tokens.json`, which is never in git. Opening a link
once stores the token as a cookie on the phone. Limits:

- one text or voice message every 5 s and one snapshot per second, per person;
- messages up to 400 characters;
- voice uploads up to 8 MB.

`/health` is the only route that needs no token.

## Remote access (family outside the home)

```bash
./scripts/expose.sh                 # Tailscale Funnel of :7870 (stable HTTPS URL)
./scripts/expose.sh --cloudflared   # temporary URL, no account needed
```

Then regenerate the links with `--base-url <public url>`. Never expose
port 7860.


## API

All routes need a token, except `/health`:

| route | what |
|---|---|
| `GET /health` | `{"ok": true, "session": true/false}` |
| `POST /api/say` | `{"text": "..."}` read out word for word; `"mode": "ai"` lets the model say it in its own words |
| `POST /api/voice` | audio upload (webm/mp4/ogg), played on the robot |
| `GET /api/snapshot` | JPEG from the robot camera |
| `POST /api/view/start` | announces who is watching |
| `GET /api/status` | robot/session status shown on the page |
| `GET /api/phrases` | canned phrases |
| `GET /api/care/summary` | data behind `/care` |
