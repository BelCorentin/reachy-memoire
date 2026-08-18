#!/usr/bin/env python3
"""Create/update hub access tokens and print ready-to-share URLs.

Usage:
    python scripts/make_tokens.py mamie celine       # add/rotate these people
    python scripts/make_tokens.py --list             # show current people
    python scripts/make_tokens.py --remove mamie     # revoke

Tokens land in <data dir>/hub_tokens.json (gitignored). Share the printed URL
once; the page stores the token as a cookie on the person's phone.
"""

import os
import sys
import json
import secrets
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("MEMOIRE_DB_PATH", str(Path(__file__).resolve().parent.parent / "data" / "memoire.db"))

from hub.auth import tokens_path  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", help="people to add or rotate")
    ap.add_argument("--remove", nargs="*", default=[], help="people to revoke")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--base-url", default=os.getenv("MEMOIRE_HUB_URL", "http://<host>:7870"))
    args = ap.parse_args()

    path = tokens_path()
    tokens: dict[str, str] = {}
    if path.exists():
        tokens = json.loads(path.read_text(encoding="utf-8"))

    for name in args.remove:
        tokens.pop(name, None)
        print(f"revoked: {name}")
    for name in args.names:
        tokens[name] = secrets.token_urlsafe(24)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tokens, ensure_ascii=False, indent=2), encoding="utf-8")
    path.chmod(0o600)

    if args.list or not (args.names or args.remove):
        print("people:", ", ".join(sorted(tokens)) or "(none)")
        return
    for name in args.names:
        print(f"\n{name}:")
        print(f"  famille:  {args.base_url}/famille?t={tokens[name]}")
        print(f"  suivi:    {args.base_url}/care?t={tokens[name]}")


if __name__ == "__main__":
    main()
