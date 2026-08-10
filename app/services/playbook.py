"""Loads the firm's risk playbook — a small, human-editable list of acceptable
fallback positions the Risk & Ambiguity Agent checks extracted clauses against.

Deliberately a flat JSON file at the project root, not a DB table: per the spec,
3-5 hand-written rules are enough to demonstrate the concept, and a lawyer should
be able to edit this without touching the database.
"""
import json
from functools import lru_cache
from pathlib import Path

PLAYBOOK_PATH = Path(__file__).resolve().parent.parent.parent / "playbook.json"


@lru_cache(maxsize=1)
def load_playbook() -> list[dict]:
    return json.loads(PLAYBOOK_PATH.read_text())
