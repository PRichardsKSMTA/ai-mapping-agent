# app_utils/suggestion_store.py
from pathlib import Path
import json, re
from typing import Dict, List, TypedDict

SUGGESTION_FILE = Path("data/mapping_suggestions.json")


class Suggestion(TypedDict):
    template: str                 # e.g. "STANDARD_COA"
    field: str                    # e.g. "NET_CHANGE"
    type: str                     # "direct" | "formula"
    formula: str | None           # pythonic expr if type == "formula"
    columns: List[str]            # canonical source column names involved
    display: str                  # nice string for UI (optional for direct)


def _load() -> List[Suggestion]:
    if not SUGGESTION_FILE.exists():
        return []
    return json.loads(SUGGESTION_FILE.read_text())


def _save(data: List[Suggestion]) -> None:
    SUGGESTION_FILE.parent.mkdir(exist_ok=True, parents=True)
    SUGGESTION_FILE.write_text(json.dumps(data, indent=2))


# Public API ───────────────────────────────────────────────────────────
def add_suggestion(s: Suggestion) -> None:
    data = _load()
    if s not in data:                 # crude dedup
        data.append(s)
        _save(data)


def get_suggestions(template: str, field: str) -> List[Suggestion]:
    return [s for s in _load() if s["template"] == template and s["field"] == field]
