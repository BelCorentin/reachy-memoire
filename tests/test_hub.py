#!/usr/bin/env python3
"""Standalone hub tests (no pytest — run with .venv/bin/python tests/test_hub.py).

Covers: transcript DB layer, repetition detector, token auth, say/snapshot/
dashboard routes against a stubbed conversation app. Robot-free.
"""

import os
import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

TMP = tempfile.mkdtemp(prefix="memoire-test-")
os.environ["MEMOIRE_DB_PATH"] = str(Path(TMP) / "memoire.db")

from fastapi.testclient import TestClient  # noqa: E402

from hub import db  # noqa: E402
from hub.api import build_app  # noqa: E402
from hub.state import HubState  # noqa: E402

PASSED = 0


def ok(cond: bool, label: str) -> None:
    global PASSED
    assert cond, f"FAIL: {label}"
    PASSED += 1
    print(f"  ok: {label}")


# ── DB layer ────────────────────────────────────────────────────────────────

print("db layer")
db.log_transcript("user", "Où est Jeanne ?", "run1")
db.log_transcript("assistant", "Jeanne est partie faire les courses.", "run1")
db.log_transcript("user", "", "run1")  # empty → dropped
rows = db.connect().execute("SELECT role, text FROM transcript ORDER BY id").fetchall()
ok(len(rows) == 2, "empty transcript dropped, 2 rows kept")
ok(rows[0]["role"] == "user" and "Jeanne" in rows[0]["text"], "row content")

today = datetime.now().strftime("%Y-%m-%d")
with db.connect() as conn:
    conn.execute(
        "INSERT INTO journal (ts, day, kind, text) VALUES (?, ?, 'mood', 'calme ce matin')",
        (datetime.now().isoformat(timespec="seconds"), today),
    )
ok(db.journal_for_day(today)[0]["kind"] == "mood", "journal_for_day")
counts = db.daily_counts(14)
ok(len(counts) == 14 and counts[-1]["day"] == today, "daily_counts covers 14 days")
ok(counts[-1]["turns"] == 1, "only user turns counted")

# ── repetition detector ─────────────────────────────────────────────────────

print("repetition detector")
now = datetime.now()
with db.connect() as conn:
    for i in range(4):  # 4 close variants of the same question, this week
        ts = (now - timedelta(days=i)).isoformat(timespec="seconds")
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        conn.execute(
            "INSERT INTO transcript (ts, day, run_id, role, text) VALUES (?, ?, 'r', 'user', ?)",
            (ts, day, ["Où est Jeanne ?", "Ou est jeanne", "Où est Jeanne dis-moi ?",
                       "où est jeanne ?"][i]),
        )
    conn.execute(
        "INSERT INTO transcript (ts, day, run_id, role, text) VALUES (?, ?, 'r', 'user', ?)",
        (now.isoformat(timespec="seconds"), today, "Quel temps fait-il aujourd'hui ?"),
    )
reps = db.repeated_utterances(30, min_count=3)
ok(len(reps) >= 1, "cluster found")
top = reps[0]
ok(top["count"] >= 4, f"cluster count >= 4 (got {top['count']})")
ok("jeanne" in top["example"].lower(), "cluster example is the Jeanne question")
ok(all("quel temps" not in c["example"].lower() for c in reps), "singleton not clustered")

# ── API ─────────────────────────────────────────────────────────────────────

print("api")


class StubHandler:
    def __init__(self):
        self.said: list[str] = []

    def _is_connected(self):
        return True

    async def say(self, text):
        self.said.append(text)


class StubMedia:
    def get_frame_jpeg(self):
        return b"\xff\xd8fakejpeg"


class StubRobot:
    media = StubMedia()


class StubStream:
    def __init__(self):
        self.handler = StubHandler()
        self._robot = StubRobot()
        self._asyncio_loop = None
        self.cleared = 0

    def clear_audio_queue(self):
        self.cleared += 1


state = HubState()
stream = StubStream()
state.attach(stream)

tokens_file = Path(TMP) / "hub_tokens.json"
tokens_file.write_text(json.dumps({"mamie": "secret-mamie", "celine": "secret-celine"}))

client = TestClient(build_app(state))

ok(client.get("/health").json()["ok"] is True, "health, no auth needed")
ok(client.get("/famille").status_code == 401, "famille without token → 401")
ok(client.get("/api/snapshot").status_code == 401, "snapshot without token → 401")

r = client.get("/famille", params={"t": "secret-mamie"})
ok(r.status_code == 200 and "Mamie" in r.text, "famille page renders with name")
ok("memoire_hub" in r.cookies, "?t= sets auth cookie")

hdr = {"Authorization": "Bearer secret-mamie"}
r = client.post("/api/say", json={"text": "Bonjour Papi !"}, headers=hdr)
ok(r.status_code == 200, "say accepted")
ok(stream.cleared == 1, "say barged in (audio queue cleared)")
ok(any("Bonjour Papi" in s and "Mamie" in s for s in stream.handler.said),
   "say wraps message with sender name")
r = client.post("/api/say", json={"text": "encore"}, headers=hdr)
ok(r.status_code == 429, "say rate-limited (5s)")
r = client.post("/api/say", json={"text": "x" * 500}, headers=hdr)
ok(r.status_code == 422, "say length-capped")

r = client.get("/api/snapshot", headers=hdr)
ok(r.status_code == 200 and r.content.startswith(b"\xff\xd8"), "snapshot returns jpeg")
r = client.get("/api/snapshot", headers={"Authorization": "Bearer secret-celine"})
ok(r.status_code == 200, "rate limit is per-person")

r = client.get("/care", headers=hdr)
ok(r.status_code == 200 and "Suivi" in r.text, "care page renders")
ok("jeanne" in r.text.lower(), "care page shows repeated question")
r = client.get("/api/care/summary", headers=hdr)
ok(r.status_code == 200 and len(r.json()["daily"]) == 14, "summary json")
ok(client.get("/api/phrases", headers=hdr).status_code == 200, "phrases endpoint")

# disconnected session → 503
stream.handler._is_connected = lambda: False
r = client.post("/api/say", json={"text": "test"},
                headers={"Authorization": "Bearer secret-celine"})
ok(r.status_code == 503, "say without session → 503")

print(f"\nALL {PASSED} CHECKS PASSED")
