from __future__ import annotations
import difflib
import math
from typing import List, Dict

from app_utils.ai.embedding import embed


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / mag if mag else 0.0


def _best_embedding_match(val: str, candidates: List[str]) -> str | None:
    val_emb = embed(val)
    best, best_sim = None, 0.0
    for c in candidates:
        sim = _cosine(val_emb, embed(c))
        if sim > best_sim:
            best, best_sim = c, sim
    return best if best_sim >= 0.60 else None  # 60 % similarity threshold


def suggest_lookup_mapping(
    source_values: List[str], dictionary_values: List[str]
) -> Dict[str, str]:
    """
    Return dict {source_value: best_dictionary_value_or_""}
    """
    mapping: Dict[str, str] = {}
    lowered = {d.lower(): d for d in dictionary_values}

    for val in source_values:
        # 1) exact case-insensitive
        if val.lower() in lowered:
            mapping[val] = lowered[val.lower()]
            continue

        # 2) cheap Levenshtein via difflib
        close = difflib.get_close_matches(val, dictionary_values, n=1, cutoff=0.85)
        if close:
            mapping[val] = close[0]
            continue

        # 3) embedding similarity
        emb_match = _best_embedding_match(val, dictionary_values)
        mapping[val] = emb_match or ""

    return mapping
