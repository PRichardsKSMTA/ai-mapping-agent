from __future__ import annotations

"""Header mapping helpers used by the microservice."""

from typing import Iterable
import re
from difflib import get_close_matches, SequenceMatcher

from ..ai import chat_json

_ABBREV_MAP: dict[str, set[str]] = {
    "zip": {"zipcode", "postal"},
    "zipcode": {"zip", "postal"},
    "code": {"cd"},
    "cd": {"code"},
    "number": {"num", "no"},
    "num": {"number", "no"},
    "no": {"number", "num"},
}


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[A-Za-z0-9]+", text.lower())
    expanded: set[str] = set()
    for tok in tokens:
        expanded.add(tok)
        expanded.update(_ABBREV_MAP.get(tok, set()))
    return expanded


def _token_similarity(a: set[str], b: set[str]) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def suggest_header_mapping(template_fields: list[str], source_columns: list[str]) -> dict[str, dict[str, float]]:
    """Return fuzzy header suggestions with confidence scores."""
    out: dict[str, dict[str, float]] = {}
    lower_map = {c.lower(): c for c in source_columns}
    lower_list = list(lower_map.keys())

    for tf in template_fields:
        if tf.startswith("ADHOC"):
            out[tf] = {}
            continue
        matches = get_close_matches(tf.lower(), lower_list, n=1, cutoff=0)
        if matches:
            best_lower = matches[0]
            best_src = lower_map[best_lower]
            ratio = SequenceMatcher(None, tf.lower(), best_lower).ratio()
            if ratio >= 0.75:
                out[tf] = {"src": best_src, "confidence": ratio}
                continue

        tf_tokens = _tokenize(tf)
        best_src = None
        best_score = 0.0
        for col in source_columns:
            score = _token_similarity(tf_tokens, _tokenize(col))
            if score > best_score:
                best_score = score
                best_src = col
        if best_score >= 0.6 and best_src:
            out[tf] = {"src": best_src, "confidence": best_score}
        else:
            out[tf] = {}

    return out


def gpt_header_completion(unmapped: list[str], source_columns: list[str]) -> dict[str, str]:
    """Return GPT suggestions mapping template fields to source columns."""
    if not unmapped:
        return {}
    system = (
        "You map template field names to the closest matching source column names. "
        "Return a JSON object {field: column_or_empty_string}."
    )
    payload = {"fields": unmapped, "columns": source_columns}
    return chat_json(system, payload)


def apply_gpt_header_fallback(
    mapping: dict[str, dict[str, str | float]],
    source_columns: list[str],
    targets: Iterable[str] | None = None,
) -> dict[str, dict[str, str | float]]:
    """Fill unmapped header fields using GPT suggestions."""
    unmapped = [k for k, v in mapping.items() if not v.get("src") and not v.get("expr")]
    if targets:
        target_set = set(targets)
        unmapped = [k for k in unmapped if k in target_set]
    if not unmapped:
        return mapping
    suggestions = gpt_header_completion(unmapped, source_columns)
    for field, col in suggestions.items():
        if col:
            mapping[field] = {"src": col}
    return mapping


def suggest_mapping(
    template_fields: list[dict],
    source_columns: list[str],
    settings: dict | None = None,
) -> tuple[dict[str, dict[str, str | float]], list[str]]:
    """Return header suggestions and list of required fields still unmapped."""
    field_keys = [f["key"] for f in template_fields]
    mapping = suggest_header_mapping(field_keys, source_columns)
    required = [f["key"] for f in template_fields if f.get("required")]
    if settings and settings.get("gpt_fallback"):
        try:
            mapping = apply_gpt_header_fallback(mapping, source_columns, targets=required)
        except Exception:
            pass
    unmapped_required = [
        k
        for k in required
        if not mapping.get(k, {}).get("src") and not mapping.get(k, {}).get("expr")
    ]
    return mapping, unmapped_required
