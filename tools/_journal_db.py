"""Shared SQLite helpers for the memoire journal tools.

Underscore-prefixed so the app's external-tool scanner ignores it; the tool
modules load it by file path (they run outside any package, so no relative
imports).
"""

import os
import sqlite3
from pathlib import Path


KINDS = ("visit", "meal", "medication", "mood", "activity", "note")


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
    return conn
