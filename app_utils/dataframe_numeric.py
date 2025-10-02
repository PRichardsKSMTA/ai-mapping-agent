from __future__ import annotations

"""DataFrame numeric coercion helpers."""

import pandas as pd


def coerce_numeric_like(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with numeric-like columns coerced to numeric dtypes.

    Each column is converted via :func:`pandas.to_numeric` with ``errors="coerce"``.
    If the conversion would result in an all-``NaN`` column, the original values are
    preserved so that true text fields remain untouched.
    """

    out = df.copy()
    for column in out.columns:
        converted = pd.to_numeric(out[column], errors="coerce")
        if converted.notna().any():
            out[column] = converted
    return out

