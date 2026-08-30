"""Shared loader for the underscore-prefixed DB module.

External tool files run outside any package, so they cannot use relative
imports (Field Log #4). Each one loads the DB helpers by file path; this keeps
that incantation in one place. Underscore-prefixed so the app's tool scanner
skips it.
"""

import sys
import importlib.util
from pathlib import Path

_DB_MODULE_NAME = "reachy_memoire_journal_db"


def journal_db():
    module = sys.modules.get(_DB_MODULE_NAME)
    if module is not None:
        return module
    spec = importlib.util.spec_from_file_location(
        _DB_MODULE_NAME, Path(__file__).with_name("_journal_db.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[_DB_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module
