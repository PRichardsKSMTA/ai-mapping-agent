from __future__ import annotations

"""DataFrame transformation utilities."""

from typing import Any
import pandas as pd


def apply_header_mappings(df: pd.DataFrame, template: Any) -> pd.DataFrame:
    """Return a new DataFrame with columns renamed per template mappings.

    Handles both direct header mappings and computed expressions.
    """
    out = df.copy()
    for layer in getattr(template, "layers", []):
        if getattr(layer, "type", None) != "header":
            continue
        for field in getattr(layer, "fields", []):
            src = getattr(field, "source", None)
            expr = getattr(field, "expression", None)
            if expr:
                # Expressions take precedence over ``source`` when provided.
                out[field.key] = eval(expr, {"df": out})  # controlled templates
            elif src and src in out.columns:
                # Copy values to the destination key without removing the original
                out[field.key] = out[src]
    if "Lane ID" not in out.columns and "LANE_ID" not in out.columns:
        out["Lane ID"] = range(1, len(out) + 1)
    return out
