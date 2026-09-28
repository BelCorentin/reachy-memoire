# Install on the robot

This is the deployment that matters outside a lab. Mémoire runs **on the
Raspberry Pi inside Reachy Mini** as a systemd service that starts at boot.
All you need is a power cable and a Wi-Fi network (a phone hotspot is enough).
No laptop has to stay in the room.

It installs **next to** Pollen's software and never replaces anything: the
robot's `reachy-mini-daemon.service` and its `/venvs/*` are left untouched.

## Install (one command, safe to re-run)

From any computer on the same network as the robot:

```bash
ssh pollen@reachy-mini.local \
  "HF_TOKEN=$(cat ~/.cache/huggingface/token) ROBOT_SUDO_PASS=root bash -s" \
  < scripts/install_on_robot.sh
```

No local clone? Pipe the script straight from GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/BelCorentin/reachy-memoire/master/scripts/install_on_robot.sh \
  | ssh pollen@reachy-mini.local "HF_TOKEN=hf_... ROBOT_SUDO_PASS=root bash -s"
```

The script:

1. installs `ffmpeg` (the only system package missing from the robot image);
2. clones the repo to `/home/pollen/reachy-memoire` and creates its own Python 3.12
   venv with `uv`;
3. writes `HF_TOKEN` to `/etc/reachy-memoire.env` (owned by root, mode 0600,
   never in git);
4. installs and enables `reachy-memoire.service`, then waits until the hub
   answers on `:7870/health`.

It takes about 15 minutes, mostly spent downloading Python packages. Re-run it to update.

Optional knobs: `MEMOIRE_REF` (branch/tag, default `master`), `MEMOIRE_REPO`,
`MEMOIRE_DIR`.

Then create access links for the family (from the robot or from your clone,
then copy `data/hub_tokens.json` to the robot):

```bash
ssh pollen@reachy-mini.local \
  "cd reachy-memoire && .venv/bin/python scripts/make_tokens.py mamie --base-url http://reachy-mini.local:7870"
```

## What happens at boot

`After=reachy-mini-daemon.service` only orders when the units *start*: the
daemon's API answers about 18 s later, and the motors always boot disabled. So
the unit runs `scripts/wait_for_daemon.sh` first. It waits for the daemon to
report `running`, then turns on the media stack and enables the motors.

Measured on a real cold boot: daemon API ready at +18 s, service active at
+34 s, greeting spoken at **+68 s**. It uses about 600 MB of the Pi's 4 GB.

## Day to day

```bash
sudo systemctl status  reachy-memoire          # is it running?
journalctl -u reachy-memoire -f                # live logs (also logs/latest.log)
sudo systemctl restart reachy-memoire          # after changing /etc/reachy-memoire.env
curl -s http://reachy-mini.local:7870/health   # from any machine on the network
```

Settings go in `/etc/reachy-memoire.env` (one `KEY=value` per line, see
[configuration](configuration.md)), for example
`REACHY_MINI_CUSTOM_PROFILE=grandsparents`, followed by a restart.

The conversation app exits cleanly after 24 h of inactivity, or when asked to go
to sleep by voice. The service deliberately does **not** restart on a clean
exit, so wake it with `sudo systemctl restart reachy-memoire`.

## Putting the robot on a new Wi-Fi network, without a screen

If the robot finds no known network at boot, it quietly falls back to its own
access point: `reachy-mini-ap`, password `reachy-mini`, address `10.42.0.1`.
Seen from your laptop, that looks exactly like a robot that is switched off. A
Wi-Fi scan showing `reachy-mini-ap` is the tell.

The documented way back is the dashboard on `http://10.42.0.1:8000` in a
browser. To do it headless:

```bash
HOTSPOT_PSK='the-wifi-password' ./scripts/provision_hotspot.sh 'Network Name'
```

The script joins the robot's access point, sends it the credentials
(`POST /wifi/connect`), rejoins your network, then looks for the robot and
prints its status. Your computer is offline for part of this, so everything is
logged to `logs/provision-*.log`. The first argument must be both the network
to teach the robot and the name of your saved NetworkManager connection.

## Demo checklist (robot + phone hotspot only)

1. Turn the hotspot on **first**, then power the robot. It joins any network it
   already knows (`curl http://reachy-mini.local:8000/wifi/status`, field
   `known_networks`). A new hotspot has to be taught once (see above).
2. Wait about 70 s.
3. From a phone on the same hotspot, open `http://reachy-mini.local:7870/health`.
   It should return `{"ok":true,"session":true}`. `session:false` means the
   connection to the Hugging Face backend didn't open: check `HF_TOKEN` and
   internet access.
4. The robot needs internet the whole time. Conversation runs on Hugging Face,
   and the hub's text-to-speech uses Microsoft edge-tts. No internet, no speech.
