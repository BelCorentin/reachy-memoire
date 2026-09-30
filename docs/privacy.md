# Privacy and care

Mémoire listens in someone's home, and the person it is built for may not be
able to fully understand or remember what the robot does. Please read this
before installing it for someone else.

**This is a prototype companion, not a medical device.** It gives no medical
advice, does no diagnosis, and must not replace care or supervision.

## Where the data goes

| data | where it goes | kept |
|---|---|---|
| Room audio while a conversation is active | Hugging Face realtime backend (speech-to-speech model) | per the backend's terms |
| Transcripts of every final turn | `data/memoire.db` **on the robot** | until deleted (no automatic expiry yet) |
| Care journal (`memoire`), tasks (`grandsparents`) | `data/memoire.db` on the robot | until deleted |
| Long-term facts (names, habits) | upstream memory file on the robot | until `forget` or deleted |
| Text of family messages | Microsoft edge-tts (speech synthesis), then a cache on the robot | cache until deleted |
| Voice messages | robot only (`data/voicemail/`) | until deleted |
| Camera | nowhere, unless a family member opens *See* on `/famille` | snapshots are not stored |

Nothing else leaves the house. For no audio to leave the home at all, point
the app at a realtime server on your own network
(`HF_REALTIME_CONNECTION_MODE=local`, see [configuration](configuration.md)).
That path is on the roadmap.

## Built-in safeguards

- **Nobody watches silently.** When someone opens the camera view, Reachy says
  out loud who is watching.
- **Messages are attributed.** Every message played on the robot starts with
  "Message de <name>."
- **One port, with tokens.** Only the hub (7870) is meant to be reachable from
  outside, and every route except `/health` needs a per-person token that can
  be revoked (`scripts/make_tokens.py --remove`). The conversation app's own
  UI (7860) has no authentication and must never be exposed.
- **Companion, not monitor.** The `grandsparents` profile deliberately keeps no
  journal. The `memoire` profile never quizzes memory.
- **Facts, not opinions.** The caregiver dashboard shows what was said and how
  often, with no model judgement about the person.

## Before installing it for someone

- Talk it through with the person and their family: what the robot hears, who
  can see and send messages, where the data is. Get consent in the way that is
  appropriate for them, and revisit it.
- Give access links only to people the person would want. Revoke them when
  that changes.
- Decide how long transcripts are kept, and delete `data/memoire.db` (or old
  rows) accordingly.
- Remember that the robot needs to be switched off, or the service stopped,
  for it to stop listening.
