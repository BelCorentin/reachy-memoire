"""list_tasks tool: read the shared to-do list back out loud."""

import sys
import logging
import importlib.util
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


class ListTasks(Tool):
    """Read back the tasks on the shared list."""

    name = "list_tasks"
    description = (
        "Relis la liste des choses à faire. Utilise-le pour \"qu'est-ce que j'ai à faire\", "
        "\"qu'est-ce qu'il reste\", \"c'était quoi déjà pour la banque\", ou quand quelqu'un "
        "veut faire le point. Par défaut, seulement les tâches encore à faire."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["open", "done", "all"],
                "description": "Quelles tâches lire. Défaut: open (celles qui restent).",
            },
            "person": {
                "type": "string",
                "description": "Ne garder que les tâches d'une personne (optionnel).",
            },
            "query": {
                "type": "string",
                "description": "Mot-clé à chercher dans les tâches (optionnel).",
            },
            "limit": {
                "type": "integer",
                "description": "Nombre maximum de tâches (défaut 10).",
            },
        },
        "required": [],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        db = _db()
        status = kwargs.get("status") or "open"
        person = kwargs.get("person")
        query = kwargs.get("query")
        limit = int(kwargs.get("limit") or 10)

        sql = "SELECT id, status, person, due, text, details FROM tasks"
        clauses, params = [], []
        if status != "all":
            clauses.append("status = ?")
            params.append(status)
        if person:
            clauses.append("person LIKE ?")
            params.append(f"%{person}%")
        if query:
            clauses.append("(text LIKE ? OR details LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        # Oldest first: the thing that has been waiting longest is read first.
        sql += " ORDER BY created_ts ASC LIMIT ?"
        params.append(max(1, min(limit, 50)))

        with db.connect_tasks() as conn:
            rows = conn.execute(sql, params).fetchall()

        tasks = [
            {
                "id": tid,
                "status": st,
                "person": person_,
                "due": due,
                "text": text,
                "details": details,
            }
            for tid, st, person_, due, text, details in rows
        ]
        logger.info("list_tasks: status=%s -> %d tasks", status, len(tasks))
        return {"count": len(tasks), "tasks": tasks}
