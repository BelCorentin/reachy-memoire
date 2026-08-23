#!/usr/bin/env bash
# Block until the Reachy Mini daemon is answering on localhost, then prime it.
#
# Used as the systemd ExecStartPre of reachy-memoire.service. `After=` only
# orders unit *start*, and the daemon needs ~20-40 s after that before its REST
# API answers — without this the app starts, fails to connect, and burns a
# restart cycle (or worse, comes up half-connected).
#
# Exits 0 as soon as the daemon reports state "running"; exits 1 after
# MEMOIRE_DAEMON_WAIT seconds so systemd surfaces a real failure.
set -uo pipefail

HOST="${REACHY_HOST:-127.0.0.1}"
DEADLINE=$(( $(date +%s) + ${MEMOIRE_DAEMON_WAIT:-180} ))
URL="http://$HOST:8000/api/daemon/status"

echo "waiting for reachy daemon at $URL"
while :; do
  body="$(curl -s -m 5 "$URL" 2>/dev/null || true)"
  case "$body" in
    *'"state":"running"'*) echo "daemon ready"; break ;;
  esac
  if [[ $(date +%s) -ge $DEADLINE ]]; then
    echo "daemon not ready after ${MEMOIRE_DAEMON_WAIT:-180}s (last body: ${body:0:200})" >&2
    exit 1
  fi
  sleep 3
done

# Same two preflights run.sh does, but done here so a failure is attributable:
# the media stack (WebRTC signalling on :8443) is lazy, and the daemon always
# boots with motors DISABLED (moves are silently ignored — Field Log #6).
curl -s -m 10 -X POST "http://$HOST:8000/api/media/acquire" >/dev/null || true
curl -s -m 10 -X POST "http://$HOST:8000/api/motors/set_mode/enabled" >/dev/null || true
echo "media acquired, motors enabled"
