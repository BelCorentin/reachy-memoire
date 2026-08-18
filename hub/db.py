"""SQLite layer for the hub: transcript log + dashboard queries.

Shares the same database file as the journal tools (tools/_journal_db.py).
WAL mode so the tool thread, the transcript logger and hub requests can
read/write concurrently.
"""

import os
import re
import sqlite3
import unicodedata
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path


def db_path() -> Path:
    env = os.getenv("MEMOIRE_DB_PATH")
    if env:
        return Path(env).expanduser()
    data_home = os.getenv("XDG_DATA_HOME")
    root = Path(data_home).expanduser() if data_home else Path.home() / ".local" / "share"
    return root / "reachy_memoire" / "memoire.db"


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            day TEXT NOT NULL,
            kind TEXT NOT NULL,
            text TEXT NOT NULL
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_day ON journal(day)")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS transcript (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            day TEXT NOT NULL,
            run_id TEXT NOT NULL,
            role TEXT NOT NULL,
            text TEXT NOT NULL
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_transcript_day ON transcript(day)")
    conn.row_factory = sqlite3.Row
    return conn


def log_transcript(role: str, text: str, run_id: str) -> None:
    text = (text or "").strip()
    if not text:
        return
    now = datetime.now()
    with connect() as conn:
        conn.execute(
            "INSERT INTO transcript (ts, day, run_id, role, text) VALUES (?, ?, ?, ?, ?)",
            (now.isoformat(timespec="seconds"), now.strftime("%Y-%m-%d"), run_id, role, text),
        )


# ── dashboard queries ────────────────────────────────────────────────────────


def journal_for_day(day: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT ts, kind, text FROM journal WHERE day = ? ORDER BY ts", (day,)
        ).fetchall()
    return [dict(r) for r in rows]


def daily_counts(days: int = 14) -> list[dict]:
    """Per-day journal-kind counts + transcript turn counts, oldest first."""
    start = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    out: dict[str, dict] = {}
    for i in range(days):
        d = (datetime.now() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        out[d] = {"day": d, "kinds": {}, "turns": 0}
    with connect() as conn:
        for r in conn.execute(
            "SELECT day, kind, COUNT(*) n FROM journal WHERE day >= ? GROUP BY day, kind",
            (start,),
        ):
            if r["day"] in out:
                out[r["day"]]["kinds"][r["kind"]] = r["n"]
        for r in conn.execute(
            "SELECT day, COUNT(*) n FROM transcript WHERE day >= ? AND role = 'user' GROUP BY day",
            (start,),
        ):
            if r["day"] in out:
                out[r["day"]]["turns"] = r["n"]
    return list(out.values())


def mood_entries(days: int = 14) -> list[dict]:
    start = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    with connect() as conn:
        rows = conn.execute(
            "SELECT ts, day, text FROM journal WHERE kind = 'mood' AND day >= ? ORDER BY ts",
            (start,),
        ).fetchall()
    return [dict(r) for r in rows]


def last_events(limit: int = 8) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT ts, kind, text FROM journal ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── repetition detector ──────────────────────────────────────────────────────

_WORD_RE = re.compile(r"[^\w\s]", re.UNICODE)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = _WORD_RE.sub(" ", text)
    return " ".join(text.split())


def repeated_utterances(
    days: int = 30, min_len: int = 10, min_count: int = 3, threshold: float = 0.8
) -> list[dict]:
    """Cluster the user's utterances by fuzzy similarity; return clusters said
    >= min_count times. The rising ones are the "what is he forgetting" signal.
    """
    start = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    prev_week = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
    with connect() as conn:
        rows = conn.execute(
            "SELECT ts, day, text FROM transcript WHERE role = 'user' AND day >= ? ORDER BY ts",
            (start,),
        ).fetchall()

    clusters: list[dict] = []
    for r in rows:
        norm = _normalize(r["text"])
        if len(norm) < min_len:
            continue
        for c in clusters:
            if SequenceMatcher(None, norm, c["norm"]).ratio() >= threshold:
                c["count"] += 1
                c["last_ts"] = r["ts"]
                if r["day"] >= week_ago:
                    c["this_week"] += 1
                elif r["day"] >= prev_week:
                    c["prev_week"] += 1
                break
        else:
            clusters.append(
                {
                    "norm": norm,
                    "example": r["text"],
                    "count": 1,
                    "first_ts": r["ts"],
                    "last_ts": r["ts"],
                    "this_week": 1 if r["day"] >= week_ago else 0,
                    "prev_week": 1 if prev_week <= r["day"] < week_ago else 0,
                }
            )

    hits = [c for c in clusters if c["count"] >= min_count]
    hits.sort(key=lambda c: c["count"], reverse=True)
    for c in hits:
        del c["norm"]
    return hits
