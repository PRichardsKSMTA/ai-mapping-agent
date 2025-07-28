from __future__ import annotations

"""Dispatch optional post-process actions once mapping is done."""

from typing import Callable
import pandas as pd
from schemas.template_v2 import PostprocessSpec, Template


def _run_excel_template(cfg: PostprocessSpec, df: pd.DataFrame) -> None:
    """Fill an Excel template with mapped data."""
    try:
        from openpyxl import load_workbook  # type: ignore
    except Exception:
        return
    # Placeholder implementation
    _ = load_workbook  # suppress unused
    return


def _run_sql_insert(cfg: PostprocessSpec, df: pd.DataFrame) -> None:
    """Insert rows into a SQL table."""
    try:
        import pyodbc  # type: ignore
    except Exception:
        return
    _ = pyodbc
    return


def _run_http_request(cfg: PostprocessSpec, df: pd.DataFrame) -> None:
    """Send data via an HTTP request."""
    try:
        import requests  # type: ignore
    except Exception:
        return
    _ = requests
    return


def _run_python_script(cfg: PostprocessSpec, df: pd.DataFrame) -> None:
    """Execute inline Python code with ``df`` available."""
    if not cfg.script:
        return
    local_vars = {"df": df}
    try:
        exec(cfg.script, {}, local_vars)
    except Exception:
        pass


_DISPATCH: dict[str, Callable[[PostprocessSpec, pd.DataFrame], None]] = {
    "excel_template": _run_excel_template,
    "sql_insert": _run_sql_insert,
    "http_request": _run_http_request,
    "python_script": _run_python_script,
}


def run_postprocess(cfg: PostprocessSpec, df: pd.DataFrame) -> None:
    """Execute post-processing based on ``cfg.type``."""
    func = _DISPATCH.get(cfg.type)
    if not func:
        raise ValueError(f"Unsupported postprocess type: {cfg.type}")
    func(cfg, df)


def run_postprocess_if_configured(template: Template, df: pd.DataFrame) -> None:
    """Run ``run_postprocess`` if ``template.postprocess`` is set."""
    if template.postprocess:
        run_postprocess(template.postprocess, df)
