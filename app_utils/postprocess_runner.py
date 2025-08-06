from __future__ import annotations

"""Minimal post-process utility."""

from typing import List
import os
import pandas as pd
from schemas.template_v2 import PostprocessSpec, Template
from app_utils.template_builder import slugify
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
    """Run optional postprocess hooks and DB inserts based on ``template``."""

    logs: List[str] = []
    df = apply_header_mappings(df, template)
    slug = slugify(template.template_name)
    if slug == "pit-bid" and operation_cd:
        from app_utils.azure_sql import insert_pit_bid_rows

        insert_pit_bid_rows(df, operation_cd, customer_name, process_guid)
        logs.append("Inserted rows into RFP_OBJECT_DATA")
    if template.postprocess:
        run_postprocess(template.postprocess, df, logs)
    return logs
