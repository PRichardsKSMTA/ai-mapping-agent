from __future__ import annotations

from typing import BinaryIO, List
import pandas as pd
from openpyxl import load_workbook


def _copy_to_temp(uploaded_file: BinaryIO, suffix: str) -> str:
    """Write uploaded file to a temporary path and return the path."""
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        if hasattr(uploaded_file, "getbuffer"):
            tmp.write(uploaded_file.getbuffer())
        else:
            tmp.write(uploaded_file.read())
            uploaded_file.seek(0)
        return tmp.name


def detect_header_row(
    path: str,
    sheet_name: str | int | None = 0,
    max_rows: int = 50,
    min_non_empty_ratio: float = 0.5,
) -> int:
    """Scan the first ``max_rows`` rows without headers and choose the row
    index with the highest non-empty ratio ≥ ``min_non_empty_ratio``."""
    df_preview = pd.read_excel(
        path, sheet_name=sheet_name, header=None, nrows=max_rows
    )
    total_cols = df_preview.shape[1]
    best_idx: int | None = None
    best_ratio = 0.0

    for idx, row in df_preview.iterrows():
        non_empty = row.count()
        ratio = non_empty / total_cols
        if ratio > best_ratio and ratio >= min_non_empty_ratio:
            best_idx, best_ratio = idx, ratio

    return best_idx if best_idx is not None else 0


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Drop fully blank columns without headers and normalize names."""
    df.columns = df.columns.map(str)
    drop_cols = [
        c
        for c in df.columns
        if (c.strip() == "" or c.startswith("Unnamed"))
        and (df[c].isna() | (df[c] == "")).all()
    ]
    if drop_cols:
        df = df.drop(columns=drop_cols)
    df.columns = df.columns.map(str)
    return df


def list_sheets(uploaded_file: BinaryIO) -> List[str]:
    """Return visible sheet names for an uploaded CSV or Excel file."""
    if uploaded_file.name.lower().endswith((".xls", ".xlsx", ".xlsm")):
        import os

        tmp_path = _copy_to_temp(uploaded_file, ".xlsx")
        wb = load_workbook(tmp_path, read_only=True, keep_vba=True)
        try:
            return [
                ws.title
                for ws in wb.worksheets
                if ws.sheet_state == "visible"
            ]
        finally:
            wb.close()
            os.unlink(tmp_path)
    return ["Sheet1"]


def read_tabular_file(
    uploaded_file: BinaryIO, sheet_name: str | int | None = 0
) -> tuple[pd.DataFrame, list[str]]:
    """Accept a CSV or Excel file-like object and return a DataFrame and
    a list of column names."""
    if uploaded_file.name.lower().endswith((".xls", ".xlsx", ".xlsm")):
        import os

        tmp_path = _copy_to_temp(uploaded_file, ".xlsx")
        header_row = detect_header_row(tmp_path, sheet_name)
        df = pd.read_excel(
            tmp_path,
            header=header_row,
            sheet_name=sheet_name,
            dtype=str,
            keep_default_na=False,
        )
        os.unlink(tmp_path)
    else:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, dtype=str, keep_default_na=False)

    df = _clean_columns(df)
    return df, list(df.columns)
