#!/usr/bin/env bash
# Launch the conversation app with the memoire profile + external tools.
# Usage: ./run.sh [extra args for reachy-mini-conversation-app, e.g. --ui --no-camera]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export REACHY_MINI_EXTERNAL_PROFILES_DIRECTORY="$ROOT/profiles"
export REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY="$ROOT/tools"
export REACHY_MINI_CUSTOM_PROFILE="${REACHY_MINI_CUSTOM_PROFILE:-memoire}"
export AUTOLOAD_EXTERNAL_TOOLS=1
export REALTIME_TRANSCRIPTION_LANGUAGE="fr"
export MEMOIRE_DB_PATH="${MEMOIRE_DB_PATH:-$ROOT/data/memoire.db}"
export MEMOIRE_HUB_PORT="${MEMOIRE_HUB_PORT:-7870}"

if [[ ! -f "$ROOT/data/hub_tokens.json" ]]; then
  echo "note: no hub tokens yet — the family/care pages need one:" >&2
  echo "      $ROOT/.venv/bin/python scripts/make_tokens.py <name>" >&2
fi

# HF_TOKEN: export it yourself or rely on `hf auth login` cache.

# Where the daemon is, for the two preflights below. The app itself finds the
# robot on its own (the SDK tries localhost first, then reachy-mini.local).
# On the robot the systemd unit sets REACHY_HOST=127.0.0.1.
ROBOT_HOST="${REACHY_HOST:-reachy-mini.local}"
if ! curl -s -m5 "http://$ROBOT_HOST:8000/api/daemon/status" >/dev/null; then
  echo "No Reachy Mini daemon at $ROBOT_HOST:8000 — is the robot on and on this network?" >&2
  echo "From a laptop the app needs reachy-mini.local to resolve (mDNS can be" >&2
  echo "slow after a robot reboot: wait and retry). See docs/troubleshooting.md." >&2
  exit 1
fi

# Preflight: make sure the daemon's media stack (WebRTC signalling :8443) is up.
curl -s -m5 -X POST "http://$ROBOT_HOST:8000/api/media/acquire" >/dev/null || true

# Preflight: the daemon boots with motors DISABLED (head silently doesn't move).
curl -s -m5 -X POST "http://$ROBOT_HOST:8000/api/motors/set_mode/enabled" >/dev/null || true

PY="python3"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
fi

mkdir -p "$ROOT/logs"
LOG="$ROOT/logs/run-$(date +%F-%H%M%S).log"
ln -sf "$(basename "$LOG")" "$ROOT/logs/latest.log"
echo "Robot: $ROBOT_HOST · Log: $LOG · Hub: http://localhost:$MEMOIRE_HUB_PORT"

"$PY" "$ROOT/scripts/launch.py" "$@" 2>&1 | tee "$LOG"
