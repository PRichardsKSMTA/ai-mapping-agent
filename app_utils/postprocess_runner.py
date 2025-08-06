from __future__ import annotations

"""Minimal post-process utility."""

from typing import List
import os
import pandas as pd
from schemas.template_v2 import PostprocessSpec, Template
from app_utils.dataframe_transform import apply_header_mappings


def run_postprocess(
    cfg: PostprocessSpec, df: pd.DataFrame, log: List[str] | None = None
) -> None:
    """Send mapped data to ``cfg.url`` via HTTP POST."""
    if log is not None:
        log.append(f"POST {cfg.url}")
    if os.getenv("ENABLE_POSTPROCESS") != "1":
        if log is not None:
            log.append("Postprocess disabled")
        return
    try:
        import requests  # type: ignore
        requests.post(cfg.url, json=df.to_dict(orient="records"), timeout=10)
    except Exception as exc:  # noqa: BLE001
        if log is not None:
            log.append(f"Error: {exc}")
        raise
    else:
        if log is not None:
            log.append("Done")


def run_postprocess_if_configured(
    template: Template,
    df: pd.DataFrame,
    process_guid: str | None = None,
    operation_cd: str | None = None,
    customer_name: str | None = None,
) -> List[str]:
    """Run optional postprocess hooks based on ``template``."""

    logs: List[str] = []
    df = apply_header_mappings(df, template)
    if template.postprocess:
        run_postprocess(template.postprocess, df, logs)
    return logs
