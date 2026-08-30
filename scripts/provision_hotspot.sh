#!/usr/bin/env bash
# Teach the robot a new wifi network, from the laptop, with no desktop app.
#
# The robot falls back to its own AP (reachy-mini-ap / 10.42.0.1) whenever none
# of its known networks is in range. Provisioning therefore means: leave your
# network, join the robot's AP, POST the credentials, come back. This script
# does the whole round trip and logs it, because the laptop is offline for the
# middle of it.
#
#   HOTSPOT_PSK='...' ./scripts/provision_hotspot.sh 'Glacière Connectée '
#
# Arg 1 is the SSID to teach the robot; it must also be the name of the saved
# NetworkManager profile to return to (that is the normal case).
set -uo pipefail

SSID="${1:?usage: HOTSPOT_PSK=... $0 '<ssid>'}"
PSK="${HOTSPOT_PSK:?set HOTSPOT_PSK to the wifi password}"
AP_PROFILE="${AP_PROFILE:-reachy-mini-ap}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="$ROOT/logs/provision-$(date +%F-%H%M%S).log"
mkdir -p "$ROOT/logs"
exec > >(tee "$LOG") 2>&1

say() { printf '\n== %s\n' "$*"; }
trap 'say "interrupted — restoring $SSID"; nmcli con up "$SSID" >/dev/null 2>&1' INT TERM

say "1/5 joining the robot AP ($AP_PROFILE)"
nmcli con up "$AP_PROFILE" || { echo "!! could not join $AP_PROFILE"; exit 1; }

say "2/5 waiting for the daemon on 10.42.0.1:8000"
for _ in $(seq 1 30); do
  curl -s -m 2 -o /dev/null http://10.42.0.1:8000/wifi/status && break
done
if ! curl -s -m 3 http://10.42.0.1:8000/wifi/status; then
  echo "!! daemon unreachable on the AP — restoring $SSID"
  nmcli con up "$SSID"; exit 1
fi

say "3/5 pushing credentials for '$SSID'"
# ssid/password are scalar query params on this route, so they must be encoded.
curl -s -m 10 -o /dev/null -w 'HTTP %{http_code}\n' -X POST -G \
     --data-urlencode "ssid=$SSID" --data-urlencode "password=$PSK" \
     http://10.42.0.1:8000/wifi/connect
# The route answers immediately and connects on a background thread; the AP
# drops out from under us as soon as it succeeds, so there is nothing to poll.

say "4/5 returning to '$SSID'"
for _ in $(seq 1 10); do
  nmcli con up "$SSID" && break
done

say "5/5 looking for the robot on the new network"
SUBNET="$(ip -4 -o addr show scope global | awk '{print $4}' | cut -d/ -f1 \
          | grep -v '^172\.1[78]\.' | head -1 | cut -d. -f1-3)"
echo "subnet: ${SUBNET:-unknown}"
FOUND=""
for round in $(seq 1 20); do
  IP="$(getent hosts reachy-mini.local 2>/dev/null | awk '{print $1; exit}')"
  if [ -n "$IP" ] && curl -s -m 3 -o /dev/null "http://$IP:8000/api/daemon/status"; then
    FOUND="$IP"; break
  fi
  if [ -n "$SUBNET" ]; then
    HIT="$(for i in $(seq 1 254); do
             (curl -s -m 2 -o /dev/null "http://$SUBNET.$i:8000/api/daemon/status" \
              && echo "$SUBNET.$i") &
           done; wait)"
    [ -n "$HIT" ] && { FOUND="$(echo "$HIT" | head -1)"; break; }
  fi
  echo "round $round: not up yet"
done

if [ -n "$FOUND" ]; then
  echo "$FOUND" > "$ROOT/.last_robot_ip"
  say "ROBOT AT $FOUND"
  curl -s -m 5 "http://$FOUND:8000/wifi/status"; echo
  curl -s -m 5 "http://$FOUND:7870/health"; echo
else
  say "robot did not appear — is 'reachy-mini-ap' still broadcasting?"
  nmcli -t -f SSID dev wifi list --rescan yes | grep -c reachy-mini-ap
  exit 1
fi
