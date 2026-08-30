"""complete_task tool: tick something off the shared list."""

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


class CompleteTask(Tool):
    """Mark a task done, by id or by matching its text."""

    name = "complete_task"
    description = (
        "Marque une tâche comme faite. Utilise-le quand quelqu'un dit qu'il a fait quelque "
        "chose (\"c'est fait\", \"je suis passé à la banque\"). Donne 'task_id' si tu le "
        "connais, sinon 'query' avec quelques mots de la tâche."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "integer",
                "description": "Identifiant de la tâche, si connu.",
            },
            "query": {
                "type": "string",
                "description": "Quelques mots de la tâche, si l'identifiant est inconnu.",
            },
        },
        "required": [],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        db = _db()
        task_id = kwargs.get("task_id")
        query = (kwargs.get("query") or "").strip()
        if task_id is None and not query:
            return {"error": "give task_id or query"}

        now = dt.datetime.now().isoformat(timespec="seconds")
        with db.connect_tasks() as conn:
            if task_id is None:
                # Ambiguity is answered by the model asking, not guessed here.
                rows = conn.execute(
                    "SELECT id, text FROM tasks WHERE status = 'open' AND text LIKE ?"
                    " ORDER BY created_ts ASC",
                    (f"%{query}%",),
                ).fetchall()
                if not rows:
                    return {"done": False, "reason": "no open task matches", "query": query}
                if len(rows) > 1:
                    return {
                        "done": False,
                        "reason": "several open tasks match — ask which one",
                        "candidates": [{"id": r[0], "text": r[1]} for r in rows[:5]],
                    }
                task_id = rows[0][0]

            cur = conn.execute(
                "UPDATE tasks SET status = 'done', done_ts = ? WHERE id = ? AND status = 'open'",
                (now, task_id),
            )
            if cur.rowcount == 0:
                return {"done": False, "reason": "no open task with that id", "id": task_id}
            text = conn.execute("SELECT text FROM tasks WHERE id = ?", (task_id,)).fetchone()[0]

        logger.info("complete_task: #%s %s", task_id, text[:120])
        return {"done": True, "id": task_id, "text": text}
