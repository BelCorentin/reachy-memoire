"""add_task tool: write down something the grandparents need to do."""

import sys
import logging
import importlib.util
import datetime as dt
from typing import Any
from pathlib import Path

from reachy_mini_conversation_app.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


def _db():
    name = "reachy_memoire_tools_common"
    module = sys.modules.get(name)
    if module is None:
        spec = importlib.util.spec_from_file_location(
            name, Path(__file__).with_name("_tools_common.py")
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return module.journal_db()


class AddTask(Tool):
    """Write one thing to do onto the shared list."""

    name = "add_task"
    description = (
        "Note UNE chose à faire sur la liste partagée. Utilise-le dès que quelqu'un "
        "mentionne une démarche, un rendez-vous, un achat, un appel à passer, un papier "
        "à remplir — même s'il ne demande pas explicitement de le noter. Le texte doit "
        "être court, concret et actionnable, en français. Précise 'person' si la tâche "
        "concerne clairement l'un des deux."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "La tâche, courte et concrète. Ex: \"Demander un carnet de remise de chèques à la banque\".",
            },
            "person": {
                "type": "string",
                "description": "Prénom de la personne concernée, si c'est clair. Sinon omettre.",
            },
            "due": {
                "type": "string",
                "description": "Quand, tel que dit à l'oral. Ex: \"jeudi\", \"avant la fin du mois\". Omettre si non dit.",
            },
            "details": {
                "type": "string",
                "description": "Précisions utiles obtenues en posant une question (numéro, lieu, quantité). Omettre si aucune.",
            },
        },
        "required": ["text"],
    }
    needs_response = False

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        db = _db()
        text = (kwargs.get("text") or "").strip()
        if not text:
            return {"error": "text must be non-empty"}

        person = (kwargs.get("person") or "").strip() or None
        due = (kwargs.get("due") or "").strip() or None
        details = (kwargs.get("details") or "").strip() or None

        now = dt.datetime.now()
        with db.connect_tasks() as conn:
            cur = conn.execute(
                "INSERT INTO tasks (created_ts, created_day, status, person, due, text, details)"
                " VALUES (?, ?, 'open', ?, ?, ?, ?)",
                (
                    now.isoformat(timespec="seconds"),
                    now.date().isoformat(),
                    person,
                    due,
                    text,
                    details,
                ),
            )
            task_id = cur.lastrowid
        logger.info("add_task: #%s %s", task_id, text[:120])
        return {"saved": True, "id": task_id, "text": text, "person": person, "due": due}
