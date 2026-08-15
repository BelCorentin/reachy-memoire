"""recall_journal tool: read back care-journal entries by day and/or keyword."""

import sys
import logging
import importlib.util
from typing import Any
from pathlib import Path

from reachy_mini_conversation_app.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)

_DB_MODULE_NAME = "reachy_memoire_journal_db"


def _journal_db():
    module = sys.modules.get(_DB_MODULE_NAME)
    if module is not None:
        return module
    spec = importlib.util.spec_from_file_location(_DB_MODULE_NAME, Path(__file__).with_name("_journal_db.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[_DB_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


class RecallJournal(Tool):
    """Read back journal entries by day and/or keyword."""

    name = "recall_journal"
    description = (
        "Relis le journal de bord. Utilise-le pour répondre à \"qu'est-ce que j'ai fait "
        "aujourd'hui / hier\", \"qui est venu me voir\", \"est-ce que j'ai pris mes médicaments\", "
        "ou pour te resituer en début de conversation. Filtre par jour (AAAA-MM-JJ) et/ou mot-clé."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "day": {
                "type": "string",
                "description": "Jour au format AAAA-MM-JJ. Omettre pour chercher sur tous les jours.",
            },
            "query": {
                "type": "string",
                "description": "Mot-clé à chercher dans les entrées (optionnel).",
            },
            "limit": {
                "type": "integer",
                "description": "Nombre maximum d'entrées (défaut 20).",
            },
        },
        "required": [],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        db = _journal_db()
        day = kwargs.get("day")
        query = kwargs.get("query")
        limit = int(kwargs.get("limit") or 20)

        sql = "SELECT ts, kind, text FROM journal"
        clauses, params = [], []
        if day:
            clauses.append("day = ?")
            params.append(day)
        if query:
            clauses.append("text LIKE ?")
            params.append(f"%{query}%")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(max(1, min(limit, 100)))

        with db.connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        entries = [{"ts": ts, "kind": kind, "text": text} for ts, kind, text in rows]
        logger.info("recall_journal: day=%s query=%s -> %d entries", day, query, len(entries))
        return {"count": len(entries), "entries": entries}
