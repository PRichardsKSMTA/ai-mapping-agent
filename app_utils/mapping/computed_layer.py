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

import json
import os
from copy import deepcopy
from typing import Any, Dict, List, MutableMapping
import re

import pandas as pd
from openai import OpenAI


def _direct_available(df: pd.DataFrame, candidates: List[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _derived_available(
    df: pd.DataFrame, deps: Dict[str, List[str]]
) -> Dict[str, str] | None:
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

    if strategy == "always":
        expr = formula.get("expression")
        if not expr:
            raise ValueError("'expression' required when strategy='always'")
        return {
            "resolved": True,
            "method": "derived",
            "source_cols": [],
            "expression": expr,
        }

    if strategy == "user_defined":
        expr = formula.get("expression")
        if expr:
            return {
                "resolved": True,
                "method": "derived",
                "source_cols": [],
                "expression": expr,
            }
        return {
            "resolved": False,
            "method": None,
            "source_cols": [],
            "expression": None,
        }

    if strategy != "first_available":
        raise NotImplementedError("Unsupported strategy")

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


def _convert_expression(expr: str) -> tuple[str, Dict[str, List[str]]]:
    """Return placeholder-based expression and dependency map."""
    deps: Dict[str, List[str]] = {}

    def repl(match: re.Match[str]) -> str:
        col = match.group(1)
        deps[col] = [col]
        return f"${col}"

    new_expr = re.sub(r"df\['([^']+)'\]", repl, expr)
    return new_expr, deps


def persist_expression_from_state(
    layer: Dict[str, Any], idx: int, state: MutableMapping[str, Any]
) -> Dict[str, Any]:
    """Return ``layer`` with user expressions appended as candidates."""
    new_layer = deepcopy(layer)
    key = f"computed_result_{idx}"
    result = state.get(key)
    if not (result and result.get("resolved") and result.get("expression")):
        return new_layer

    expr, deps = _convert_expression(result["expression"])
    formula = new_layer.setdefault("formula", {})

    if formula.get("strategy") != "first_available":
        formula.clear()
        formula["strategy"] = "first_available"
        formula["candidates"] = [
            {"type": "direct", "source_candidates": [new_layer.get("target_field")]}]
    formula.pop("expression", None)
    formula.pop("dependencies", None)
    cands = formula.setdefault("candidates", [])
    if not any(c.get("type") == "derived" and c.get("expression") == expr for c in cands):
        cands.append({"type": "derived", "expression": expr, "dependencies": deps})

    return new_layer


def gpt_formula_suggestion(target_field: str, df: pd.DataFrame) -> str:
    """Return GPT-proposed expression for ``target_field``."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    client = OpenAI(api_key=api_key)
    system = (
        "Suggest a pandas expression to derive the target field from the given columns. "
        "Use df['COL'] syntax and basic arithmetic. Return only the expression string."
    )
    payload = {"target": target_field, "columns": list(df.columns)}
    resp = client.chat.completions.create(
        model="gpt-3.5-turbo-0125",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload)},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()
