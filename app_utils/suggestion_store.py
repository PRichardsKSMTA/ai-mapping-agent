# app_utils/suggestion_store.py
from pathlib import Path
import json
import re
import hashlib
from typing import List, Optional, TypedDict

SUGGESTION_FILE = (
    Path(__file__).resolve().parent.parent / "data" / "mapping_suggestions.json"
)


class Suggestion(TypedDict, total=False):
    template: str                 # e.g. "STANDARD_COA"
    field: str                    # e.g. "NET_CHANGE"
    type: str                     # "direct" | "formula"
    formula: str | None           # pythonic expr if type == "formula"
    columns: List[str]            # canonical source column names involved
    display: str                  # nice string for UI (optional for direct)
    header_id: str                # optional fingerprint of source headers


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


def _headers_id(headers: Optional[List[str]]) -> Optional[str]:
    if not headers:
        return None
    canon = "|".join(sorted(_canon(h) for h in headers))
    return hashlib.sha1(canon.encode()).hexdigest()[:8]


def add_suggestion(s: Suggestion, headers: Optional[List[str]] | None = None) -> None:
    data = _load()
    t_c = _canon(s["template"])
    f_c = _canon(s["field"])
    cols_c = [_canon(c) for c in s.get("columns", [])]
    h_id = s.get("header_id") or _headers_id(headers)
    if h_id:
        s = {**s, "header_id": h_id}
    # Replace suggestion for same header set
    for i, existing in enumerate(data):
        if (
            _canon(existing["template"]) == t_c
            and _canon(existing["field"]) == f_c
            and existing.get("header_id") == h_id
        ):
            data[i] = s
            _save(data)
            return
    # Deduplicate exact suggestions
    for existing in data:
        if (
            _canon(existing["template"]) == t_c
            and _canon(existing["field"]) == f_c
            and existing.get("type") == s.get("type")
            and existing.get("formula") == s.get("formula")
            and [_canon(c) for c in existing.get("columns", [])] == cols_c
            and existing.get("header_id") == h_id
        ):
            return
    data.append(s)
    _save(data)


def get_suggestions(
    template: str, field: str, headers: Optional[List[str]] | None = None
) -> List[Suggestion]:
    t_c = _canon(template)
    f_c = _canon(field)
    h_id = _headers_id(headers)
    matches = []
    for s in _load():
        if _canon(s["template"]) == t_c and _canon(s["field"]) == f_c:
            matches.append(s)
    if h_id:
        matches.sort(key=lambda x: 0 if x.get("header_id") == h_id else 1)
    return matches


def remove_suggestion(template: str, field: str, suggestion_type: str | None = "formula") -> None:
    """Remove stored suggestions matching ``template`` and ``field``."""
    t_c = _canon(template)
    f_c = _canon(field)
    data = [
        s
        for s in _load()
        if not (
            _canon(s["template"]) == t_c
            and _canon(s["field"]) == f_c
            and (suggestion_type is None or s.get("type") == suggestion_type)
        )
    ]
    _save(data)
