#!/usr/bin/env bash
# Launch the conversation app with the memoire profile + external tools.
# Usage: ./run.sh [extra args for reachy-mini-conversation-app, e.g. --ui --no-camera]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export REACHY_MINI_EXTERNAL_PROFILES_DIRECTORY="$ROOT/profiles"
export REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY="$ROOT/tools"
export REACHY_MINI_CUSTOM_PROFILE="memoire"
export AUTOLOAD_EXTERNAL_TOOLS=1
export REALTIME_TRANSCRIPTION_LANGUAGE="fr"
export MEMOIRE_DB_PATH="${MEMOIRE_DB_PATH:-$ROOT/data/memoire.db}"
export MEMOIRE_HUB_PORT="${MEMOIRE_HUB_PORT:-7870}"

if [[ ! -f "$ROOT/data/hub_tokens.json" ]]; then
  echo "note: no hub tokens yet — famille/care pages need one:" >&2
  echo "      $ROOT/.venv/bin/python scripts/make_tokens.py mamie" >&2
fi

# HF_TOKEN: export it yourself or rely on `hf auth login` cache.

ROBOT_HOST="${REACHY_HOST:-$(getent hosts reachy-mini.local | awk '{print $1; exit}')}"
if [[ -z "$ROBOT_HOST" ]]; then
  echo "Cannot resolve reachy-mini.local — is the robot on and on the same wifi?" >&2
  echo "(Set REACHY_HOST=<ip> to skip mDNS.)" >&2
  exit 1
fi

# Daemon 1.8.3 reports its hotspot IP as wlan_ip → SDK dials the WebRTC
# signalling server on an unroutable address (Field Log #5). Force the real one.
export REACHY_SIGNALLING_HOST="${REACHY_SIGNALLING_HOST:-$ROBOT_HOST}"

# Preflight: make sure the daemon's media stack (WebRTC signalling :8443) is up.
curl -s -m5 -X POST "http://$ROBOT_HOST:8000/api/media/acquire" >/dev/null || true

PY="python3"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
fi

mkdir -p "$ROOT/logs"
LOG="$ROOT/logs/run-$(date +%F-%H%M%S).log"
ln -sf "$(basename "$LOG")" "$ROOT/logs/latest.log"
echo "Robot: $ROBOT_HOST · Log: $LOG · Hub: http://localhost:$MEMOIRE_HUB_PORT"

"$PY" "$ROOT/scripts/launch_patched.py" "$@" 2>&1 | tee "$LOG"
