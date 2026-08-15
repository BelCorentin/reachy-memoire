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

# HF_TOKEN: export it yourself or rely on `hf auth login` cache.

exec reachy-mini-conversation-app "$@"
