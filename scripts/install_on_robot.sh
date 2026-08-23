#!/usr/bin/env bash
# Install reachy-memoire ROBOT-SIDE so it runs standalone: power on -> memoire
# runs, no laptop involved. Idempotent — safe to re-run to update.
#
# Run it ON the robot (it is written to be piped in over ssh):
#
#   # from the laptop, with the HF token and a sudo password:
#   ssh pollen@reachy-mini.local \
#     "HF_TOKEN=$(cat ~/.cache/huggingface/token) ROBOT_SUDO_PASS=root bash -s" \
#     < scripts/install_on_robot.sh
#
#   # or, after a wipe, straight from GitHub (no local clone needed):
#   curl -fsSL https://raw.githubusercontent.com/BelCorentin/reachy-memoire/master/scripts/install_on_robot.sh \
#     | ssh pollen@reachy-mini.local "HF_TOKEN=hf_... ROBOT_SUDO_PASS=root bash -s"
#
# Then push the runtime state that is NOT in git (tokens, phrases, journal):
#   rsync -av data/hub_tokens.json data/phrases.json data/memoire.db \
#         pollen@reachy-mini.local:/home/pollen/reachy-memoire/data/
#
# Env knobs:
#   HF_TOKEN         written into /etc/reachy-memoire.env (required at runtime;
#                    a placeholder is written if unset, and the script says so)
#   ROBOT_SUDO_PASS  password for sudo when there is no tty (loaner: root)
#   MEMOIRE_REPO     git URL (default: the public repo)
#   MEMOIRE_REF      branch/tag/sha to check out (default: master)
#   MEMOIRE_DIR      install dir (default: /home/pollen/reachy-memoire)
set -euo pipefail

REPO="${MEMOIRE_REPO:-https://github.com/BelCorentin/reachy-memoire.git}"
REF="${MEMOIRE_REF:-master}"
DIR="${MEMOIRE_DIR:-/home/pollen/reachy-memoire}"
ENV_FILE="/etc/reachy-memoire.env"
UNIT="reachy-memoire.service"

say() { printf '\n== %s\n' "$*"; }

# sudo without a tty: prefer NOPASSWD, else ROBOT_SUDO_PASS, else interactive.
sudo_run() {
  if sudo -n true 2>/dev/null; then
    sudo "$@"
  elif [[ -n "${ROBOT_SUDO_PASS:-}" ]]; then
    printf '%s\n' "$ROBOT_SUDO_PASS" | sudo -S -p '' "$@"
  else
    echo "!! sudo needs a password: re-run with ROBOT_SUDO_PASS=... or ssh -t" >&2
    sudo "$@"
  fi
}

# ── 0. sanity ───────────────────────────────────────────────────────────────
say "host check"
uname -m
if [[ ! -S /run/systemd/private && ! -d /run/systemd/system ]]; then
  echo "!! no systemd — this script is for the robot's Raspberry Pi OS" >&2; exit 1
fi

# uv ships with the robot image at /opt/uv; install it if a wipe removed it.
UV=""
for cand in /opt/uv/uv "$HOME/.local/bin/uv" "$(command -v uv 2>/dev/null || true)"; do
  [[ -n "$cand" && -x "$cand" ]] && { UV="$cand"; break; }
done
if [[ -z "$UV" ]]; then
  say "installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  UV="$HOME/.local/bin/uv"
fi
echo "uv: $UV ($($UV --version))"

# ── 1. system packages ──────────────────────────────────────────────────────
# ffmpeg: hub TTS (edge-tts mp3 -> WAV) and family voice messages.
if ! command -v ffmpeg >/dev/null; then
  say "installing ffmpeg"
  sudo_run apt-get update -qq
  sudo_run env DEBIAN_FRONTEND=noninteractive apt-get install -y ffmpeg
fi
echo "ffmpeg: $(ffmpeg -version 2>&1 | head -1)"

# ── 2. code ─────────────────────────────────────────────────────────────────
say "code -> $DIR ($REF)"
if [[ -d "$DIR/.git" ]]; then
  git -C "$DIR" fetch --quiet origin
  git -C "$DIR" checkout --quiet "$REF"
  git -C "$DIR" reset --hard --quiet "origin/$REF" 2>/dev/null || git -C "$DIR" reset --hard --quiet "$REF"
else
  git clone --quiet "$REPO" "$DIR"
  git -C "$DIR" checkout --quiet "$REF"
fi
git -C "$DIR" log --oneline -1
mkdir -p "$DIR/data" "$DIR/logs"

# ── 3. python env ───────────────────────────────────────────────────────────
# 3.12 to match the robot's own daemon/apps venvs; uv fetches a standalone
# build if the OS only ships 3.13. PyGObject/pycairo build from source here —
# the gir/cairo -dev packages are already on the image.
say "venv + dependencies (first run: ~10 min on the Pi)"
[[ -x "$DIR/.venv/bin/python" ]] || "$UV" venv --python 3.12 "$DIR/.venv"
"$UV" pip install --python "$DIR/.venv/bin/python" --prerelease=allow \
  "git+https://github.com/pollen-robotics/reachy_mini_conversation_app" edge-tts
"$DIR/.venv/bin/python" - <<'PY'
import reachy_mini, reachy_mini_conversation_app as app, edge_tts
print("reachy_mini", reachy_mini.__version__ if hasattr(reachy_mini, "__version__") else "?")
print("conversation_app ok, edge_tts ok")
PY

# ── 4. secrets ──────────────────────────────────────────────────────────────
# Root-owned 0600, referenced by the unit's EnvironmentFile. NEVER in git.
say "secrets -> $ENV_FILE"
if [[ -n "${HF_TOKEN:-}" ]]; then
  printf 'HF_TOKEN=%s\n' "$HF_TOKEN" | sudo_run tee "$ENV_FILE" >/dev/null
  echo "HF_TOKEN written"
elif sudo_run test -s "$ENV_FILE"; then
  echo "kept existing $ENV_FILE"
else
  printf 'HF_TOKEN=REPLACE_ME\n' | sudo_run tee "$ENV_FILE" >/dev/null
  echo "!! no HF_TOKEN given — wrote a placeholder. Inference will NOT work until:"
  echo "   ssh pollen@reachy-mini.local \"echo 'HF_TOKEN=hf_...' | sudo tee $ENV_FILE\""
fi
sudo_run chmod 600 "$ENV_FILE"
sudo_run chown root:root "$ENV_FILE"

# ── 5. systemd unit ─────────────────────────────────────────────────────────
say "systemd unit"
chmod +x "$DIR/run.sh" "$DIR/scripts/wait_for_daemon.sh"
sudo_run install -m 644 "$DIR/scripts/$UNIT" "/etc/systemd/system/$UNIT"
sudo_run systemctl daemon-reload
sudo_run systemctl enable "$UNIT"
sudo_run systemctl restart "$UNIT"

# ── 6. verify ───────────────────────────────────────────────────────────────
say "waiting for the hub on :7870"
for _ in $(seq 1 60); do
  if curl -s -m 3 http://127.0.0.1:7870/health >/dev/null 2>&1; then
    echo "hub up: $(curl -s -m 3 http://127.0.0.1:7870/health)"
    break
  fi
  sleep 5
done
systemctl --no-pager --lines=0 status "$UNIT" || true

if [[ ! -s "$DIR/data/hub_tokens.json" ]]; then
  echo
  echo "note: no hub tokens on the robot yet — /famille and /care will 401."
  echo "      copy them from the laptop, or create new ones:"
  echo "      $DIR/.venv/bin/python $DIR/scripts/make_tokens.py mamie \\"
  echo "        --base-url http://reachy-mini.local:7870"
fi

say "done — logs: journalctl -u $UNIT -f"
