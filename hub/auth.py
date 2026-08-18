"""Token auth + rate limiting for the hub.

Tokens live in ``<data dir>/hub_tokens.json`` — ``{"mamie": "<secret>", ...}``.
Generate with ``scripts/make_tokens.py``. Every route except /health requires
one, presented as (in priority order) Authorization: Bearer, ``?t=`` query
(pages then set a cookie), or the ``memoire_hub`` cookie.
"""

import hmac
import json
import time
import threading
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Request

from . import db

COOKIE_NAME = "memoire_hub"


def tokens_path() -> Path:
    return db.db_path().parent / "hub_tokens.json"


def load_tokens() -> dict[str, str]:
    path = tokens_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in data.items() if v}
    except Exception:
        return {}


def _match(token: str) -> Optional[str]:
    for name, secret in load_tokens().items():
        if hmac.compare_digest(token, secret):
            return name
    return None


def request_token(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    q = request.query_params.get("t")
    if q:
        return q
    return request.cookies.get(COOKIE_NAME)


def require_person(request: Request) -> str:
    """FastAPI dependency: resolve the caller's token to a person name."""
    token = request_token(request)
    person = _match(token) if token else None
    if person is None:
        raise HTTPException(status_code=401, detail="token invalide ou manquant")
    return person


class RateLimiter:
    """Minimal fixed-interval limiter, keyed by (bucket, person)."""

    def __init__(self) -> None:
        self._last: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()

    def check(self, bucket: str, person: str, interval_s: float) -> None:
        now = time.monotonic()
        key = (bucket, person)
        with self._lock:
            last = self._last.get(key, 0.0)
            if now - last < interval_s:
                raise HTTPException(status_code=429, detail="trop de requêtes, réessayez")
            self._last[key] = now
