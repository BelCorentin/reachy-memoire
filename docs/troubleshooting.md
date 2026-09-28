# Troubleshooting

These are pitfalls actually hit on a Reachy Mini Wireless (daemon 1.8.3 → 1.9.0,
SDK 1.10.0rc5/rc6, August 2026). Most of them fail **silently**, so each entry
says how to recognise it.

## The head doesn't move at all

**Cause.** The daemon boots with its motors disabled (`motor_control_mode:
disabled`). Moves are accepted without any error and simply ignored.

**Fix.** `curl -X POST http://<robot>:8000/api/motors/set_mode/enabled`.
`run.sh` and the boot service already do this. The motors are disabled again
after every daemon update.

## Commands succeed but nothing moves, after a daemon update

**Symptom.** After a self-update, every command returns an id and
`nb_error: 0`, and the logs show no errors, yet the encoders never change.
`/api/move/running` stays empty. The tell is `control_loop_stats.write_dt`
around 0.07 ms (healthy is around 0.4 ms).

**Fix.** `POST /api/daemon/restart`, then enable the motors again.

**General rule.** "Command accepted" doesn't prove the robot moved. Check by
reading the pose back (`/api/state/present_head_pose` before and after).

## Face tracking never finds anyone

The daemon's face tracker only exists from **daemon 1.9.0**. Older daemons drop
the command silently, and `get_tracked_face()` returns `detected=False,
ts=None` forever. Update with `curl -X POST http://<robot>:8000/update/start`.
The update routes have no `/api` prefix.

## The robot can't be found on the network

- **It is on its own access point.** With no known Wi-Fi in range, it falls
  back to `reachy-mini-ap` without telling you. See
  [install-on-robot.md](install-on-robot.md#putting-the-robot-on-a-new-wi-fi-network-without-a-screen).
- **mDNS is slow after a reboot.** `reachy-mini.local` can take a while to
  resolve again on the laptop. Wait and retry. In laptop mode the app itself
  needs that name to resolve. When Mémoire runs on the robot, this problem
  doesn't exist.

## Audio/video times out while motion works (laptop mode)

- The media stack starts lazily: `curl -X POST http://<robot>:8000/api/media/acquire`
  (`run.sh` does this).
- On daemon **1.8.3** only, `/api/daemon/status` reports the robot's
  access-point address (`10.42.0.1`) as `wlan_ip`, so the SDK tries to open
  media on an unreachable address. Update the daemon to ≥ 1.9.0. This doesn't
  happen when Mémoire runs on the robot.

## Reachy keeps cutting itself off

This happens when several people talk in the room. See
[turn detection](configuration.md#turn-detection).

## Units: degrees vs radians

`reachy_mini.utils.create_head_pose()` takes **degrees** by default. Every
other angle in the SDK (`set_target`, `goto_target`, antennas, `body_yaw`)
takes **radians**. Mixing them raises no error: the joints just go to their
limits.

## Where things are logged and stored

| what | where |
|---|---|
| app log | `logs/run-<timestamp>.log`, `logs/latest.log`; on the robot also `journalctl -u reachy-memoire` |
| journal, tasks, transcripts | `data/memoire.db` (SQLite) |
| hub tokens, canned phrases | `data/hub_tokens.json`, `data/phrases.json` |
| speech cache, voice messages | `data/tts_cache/`, `data/voicemail/` |
| long-term facts (`remember` tool, upstream) | `~/.local/share/reachy_mini_conversation_app/memory.v1.json` |
| robot daemon | `journalctl -u reachy-mini-daemon` on the robot |

`data/` and `logs/` are never committed.
