"""journal_event tool: record one dated entry in the care journal."""

import sys
import logging
import importlib.util
import datetime as dt
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


class JournalEvent(Tool):
    """Record one dated entry in the care journal."""

    name = "journal_event"
    description = (
        "Écris UNE entrée datée dans le journal de bord (visites, repas, médicaments, humeur, "
        "activités, remarques). Utilise-le discrètement dès qu'un moment notable se produit, "
        "sans annoncer que tu l'enregistres. Une entrée = un fait court en français, à la "
        "troisième personne."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "enum": ["visit", "meal", "medication", "mood", "activity", "note"],
                "description": "Catégorie de l'entrée.",
            },
            "text": {
                "type": "string",
                "description": "Le fait, court et factuel. Ex: \"Visite de sa fille Claire, très contente.\"",
            },
        },
        "required": ["kind", "text"],
    }
    needs_response = False

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        db = _journal_db()
        kind = kwargs.get("kind")
        text = (kwargs.get("text") or "").strip()
        if kind not in db.KINDS or not text:
            return {"error": f"kind must be one of {db.KINDS} and text non-empty"}

        now = dt.datetime.now()
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO journal (ts, day, kind, text) VALUES (?, ?, ?, ?)",
                (now.isoformat(timespec="seconds"), now.date().isoformat(), kind, text),
            )
        logger.info("journal_event: [%s] %s", kind, text[:120])
        return {"saved": True, "kind": kind, "text": text}
