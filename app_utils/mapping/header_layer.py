from __future__ import annotations
"""Header mapping helpers including GPT fallback."""

from typing import Dict, List, Iterable
import os
import json
from openai import OpenAI



def gpt_header_completion(unmapped: List[str], source_columns: List[str]) -> Dict[str, str]:
    """Return GPT suggestions mapping template fields to source columns."""
    if not unmapped:
        return {}
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    client = OpenAI(api_key=api_key)
    system = (
        "You map template field names to the closest matching source column names. "
        "Return a JSON object {field: column_or_empty_string}."
    )
    payload = {"fields": unmapped, "columns": source_columns}
    resp = client.chat.completions.create(
        model="gpt-3.5-turbo-0125",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload)},
        ],
        temperature=0.2,
    )
    return json.loads(resp.choices[0].message.content)


def apply_gpt_header_fallback(
    mapping: Dict[str, Dict[str, str]],
    source_columns: List[str],
    targets: Iterable[str] | None = None,
) -> Dict[str, Dict[str, str]]:
    """Fill unmapped header fields using GPT suggestions.

    Parameters
    ----------
    mapping:
        Existing field mapping.
    source_columns:
        Available source columns.
    targets:
        Specific field keys to consider. If empty or ``None`` all unmapped
        fields are targeted.
    """
    unmapped = [k for k, v in mapping.items() if not v.get("src") and not v.get("expr")]
    if targets:
        target_set = set(targets)
        unmapped = [k for k in unmapped if k in target_set]
    if not unmapped:
        return mapping
    try:
        suggestions = gpt_header_completion(unmapped, source_columns)
    except Exception:
        return mapping
    for field, col in suggestions.items():
        if col:
            mapping[field] = {"src": col}
    return mapping
