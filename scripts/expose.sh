#!/usr/bin/env bash
# Expose the memoire hub (port 7870 ONLY — never 7860, the upstream UI has no
# auth) to the internet over HTTPS, for the family PWA and the care dashboard.
#
# Preferred: Tailscale Funnel (stable URL, TLS handled, free):
#   sudo apt install tailscale && sudo tailscale up
#   ./scripts/expose.sh                # runs: tailscale funnel 7870
#
# Fallback: cloudflared quick tunnel (URL changes every run):
#   ./scripts/expose.sh --cloudflared
set -euo pipefail

PORT="${MEMOIRE_HUB_PORT:-7870}"

if [[ "${1:-}" == "--cloudflared" ]]; then
  command -v cloudflared >/dev/null || {
    echo "cloudflared not installed: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/" >&2
    exit 1
  }
  exec cloudflared tunnel --url "http://localhost:$PORT"
fi

command -v tailscale >/dev/null || {
  echo "tailscale not installed. Either:" >&2
  echo "  sudo apt install tailscale && sudo tailscale up   # then rerun" >&2
  echo "  ./scripts/expose.sh --cloudflared                 # ephemeral fallback" >&2
  exit 1
}

echo "Funnel URL will be https://<machine>.<tailnet>.ts.net/ → hub :$PORT"
echo "Generate share links with: python scripts/make_tokens.py <name> --base-url <funnel url>"
exec tailscale funnel "$PORT"
