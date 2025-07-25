"""
computed_layer.py
-----------------
Evaluate and execute a computed layer spec at runtime.

Current capabilities
• strategy == "first_available"
    Iterate candidates in order:
        - if type == "direct": returns the first source column that exists
        - if type == "derived": checks expression & dependencies present
• Returns a dict:
    {
        "resolved": bool,
        "method": "direct" | "derived" | None,
        "source_cols": List[str],
        "expression": str | None
    }
"""

from __future__ import annotations
from copy import deepcopy
from typing import Dict, Any, List, MutableMapping

import pandas as pd


def _direct_available(df: pd.DataFrame, candidates: List[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _derived_available(df: pd.DataFrame, deps: Dict[str, List[str]]) -> Dict[str, str] | None:
    mapping = {}
    for placeholder, variants in deps.items():
        hit = _direct_available(df, variants)
        if not hit:
            return None
        mapping[placeholder] = hit
    return mapping


def resolve_computed_layer(layer: Dict[str, Any], df: pd.DataFrame) -> Dict[str, Any]:
    """
    Returns resolution info dict (see docstring above).
    """
    formula = layer["formula"]
    strategy = formula.get("strategy", "first_available")

    if strategy != "first_available":
        raise NotImplementedError("Only first_available strategy supported")

    for cand in formula["candidates"]:
        if cand["type"] == "direct":
            src = _direct_available(df, cand["source_candidates"])
            if src:
                return {
                    "resolved": True,
                    "method": "direct",
                    "source_cols": [src],
                    "expression": None,
                }

        elif cand["type"] == "derived":
            mapping = _derived_available(df, cand["dependencies"])
            if mapping:
                expr = cand["expression"]
                for ph, col in mapping.items():
                    expr = expr.replace(f"${ph}", f"df['{col}']")
                return {
                    "resolved": True,
                    "method": "derived",
                    "source_cols": list(mapping.values()),
                    "expression": expr,
                }

    # None matched
    return {
        "resolved": False,
        "method": None,
        "source_cols": [],
        "expression": None,
    }


def persist_expression_from_state(
    layer: Dict[str, Any], idx: int, state: MutableMapping[str, Any]
) -> Dict[str, Any]:
    """Return a copy of ``layer`` with user expression injected."""
    new_layer = deepcopy(layer)
    key = f"computed_result_{idx}"
    result = state.get(key)
    if result and result.get("resolved") and result.get("expression"):
        new_layer.setdefault("formula", {})["expression"] = result["expression"]
    return new_layer

