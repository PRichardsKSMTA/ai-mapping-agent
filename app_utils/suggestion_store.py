# app_utils/suggestion_store.py
from pathlib import Path
import json
import re
from typing import List, TypedDict

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
def _canon(text: str) -> str:
    """Return lowercase string with all whitespace removed."""
    return re.sub(r"\s+", "", text).lower()


def add_suggestion(s: Suggestion) -> None:
    data = _load()
    t_c = _canon(s["template"])
    f_c = _canon(s["field"])
    cols_c = [_canon(c) for c in s.get("columns", [])]
    for existing in data:
        if (
            _canon(existing["template"]) == t_c
            and _canon(existing["field"]) == f_c
            and existing.get("type") == s.get("type")
            and existing.get("formula") == s.get("formula")
            and [_canon(c) for c in existing.get("columns", [])] == cols_c
        ):
            return
    data.append(s)
    _save(data)


def get_suggestions(template: str, field: str) -> List[Suggestion]:
    t_c = _canon(template)
    f_c = _canon(field)
    return [
        s
        for s in _load()
        if _canon(s["template"]) == t_c and _canon(s["field"]) == f_c
    ]
