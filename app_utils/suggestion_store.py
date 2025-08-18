"""Persistence layer for field mapping suggestions.

This module stores per-template field mapping suggestions on disk. It exposes
helpers to add, fetch, update, and delete individual suggestions.

Key functions
-------------
``add_suggestion``
    Persist a new suggestion if it doesn't already exist.
``get_suggestions``
    Return all suggestions for a template field.
``get_suggestion``
    Fetch a single suggestion matching a template field and either columns or a
    formula.
``update_suggestion``
    Modify an existing suggestion's display text or source columns.
``delete_suggestion``
    Remove one stored suggestion identified by its columns or formula.
``remove_suggestion``
    Remove all suggestions matching a template/field pair.
"""

from pathlib import Path
import json
import os
import re
import hashlib
from typing import List, Optional, TypedDict

_default_path = Path.cwd() / "data" / "mapping_suggestions.json"
SUGGESTION_FILE = Path(os.environ.get("SUGGESTION_FILE", _default_path))


class Suggestion(TypedDict, total=False):
    template: str                 # e.g. "STANDARD_COA"
    field: str                    # e.g. "NET_CHANGE"
    type: str                     # "direct" | "formula"
    formula: str | None           # pythonic expr if type == "formula"
    columns: List[str]            # canonical source column names involved
    display: str                  # nice string for UI (optional for direct)
    header_id: str                # optional fingerprint of source headers


def _load() -> List[Suggestion]:
    SUGGESTION_FILE.parent.mkdir(exist_ok=True, parents=True)
    if not SUGGESTION_FILE.exists():
        return []
    try:
        data = json.loads(SUGGESTION_FILE.read_text())
    except json.JSONDecodeError:
        return []

    seen = set()
    deduped: List[Suggestion] = []
    for s in data:
        key = (
            _canon(s.get("template", "")),
            _canon(s.get("field", "")),
            s.get("type"),
            s.get("formula"),
            tuple(_canon(c) for c in s.get("columns", [])),
            _canon(s.get("display", "")),
        )
        if key not in seen:
            seen.add(key)
            deduped.append(s)
    if len(deduped) != len(data):
        _save(deduped)
    return deduped


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
    display_c = _canon(s.get("display", ""))
    h_id = s.get("header_id") or _headers_id(headers)
    if h_id:
        s = {**s, "header_id": h_id}
    for i, existing in enumerate(data):
        if (
            _canon(existing["template"]) == t_c
            and _canon(existing["field"]) == f_c
            and existing.get("type") == s.get("type")
            and existing.get("formula") == s.get("formula")
            and [_canon(c) for c in existing.get("columns", [])] == cols_c
            and _canon(existing.get("display", "")) == display_c
        ):
            if h_id:
                data[i] = {**existing, "header_id": h_id}
                _save(data)
                return
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


def get_suggestion(
    template: str,
    field: str,
    *,
    columns: Optional[List[str]] | None = None,
    formula: str | None = None,
) -> Optional[Suggestion]:
    """Return a single suggestion matching ``template``/``field``.

    Either ``columns`` or ``formula`` must be provided to identify the
    suggestion. Matching on columns is case/whitespace insensitive.
    """

    t_c = _canon(template)
    f_c = _canon(field)
    cols_c = [_canon(c) for c in columns] if columns else None
    for s in _load():
        if _canon(s["template"]) == t_c and _canon(s["field"]) == f_c:
            match_formula = formula is not None and s.get("formula") == formula
            match_columns = (
                cols_c is not None
                and [_canon(c) for c in s.get("columns", [])] == cols_c
            )
            if match_formula or match_columns:
                return s
    return None


def update_suggestion(
    template: str,
    field: str,
    *,
    columns: Optional[List[str]] | None = None,
    formula: str | None = None,
    display: Optional[str] | None = None,
    new_columns: Optional[List[str]] | None = None,
) -> bool:
    """Update an existing suggestion's display text or columns.

    The suggestion is selected via ``template``/``field`` and either ``columns``
    or ``formula``. Returns ``True`` if a suggestion was updated.
    """

    data = _load()
    t_c = _canon(template)
    f_c = _canon(field)
    cols_c = [_canon(c) for c in columns] if columns else None
    updated = False
    for i, s in enumerate(data):
        if _canon(s["template"]) == t_c and _canon(s["field"]) == f_c:
            match_formula = formula is not None and s.get("formula") == formula
            match_columns = (
                cols_c is not None
                and [_canon(c) for c in s.get("columns", [])] == cols_c
            )
            if match_formula or match_columns:
                new_s = dict(s)
                if display is not None:
                    new_s["display"] = display
                if new_columns is not None:
                    new_s["columns"] = new_columns
                data[i] = new_s
                updated = True
                break
    if updated:
        _save(data)
    return updated


def delete_suggestion(
    template: str,
    field: str,
    *,
    columns: Optional[List[str]] | None = None,
    formula: str | None = None,
) -> bool:
    """Delete a single suggestion identified by columns or formula."""

    t_c = _canon(template)
    f_c = _canon(field)
    cols_c = [_canon(c) for c in columns] if columns else None
    new_data: List[Suggestion] = []
    removed = False
    for s in _load():
        if _canon(s["template"]) == t_c and _canon(s["field"]) == f_c:
            match_formula = formula is not None and s.get("formula") == formula
            match_columns = (
                cols_c is not None
                and [_canon(c) for c in s.get("columns", [])] == cols_c
            )
            if match_formula or match_columns:
                removed = True
                continue
        new_data.append(s)
    if removed:
        _save(new_data)
    return removed


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
