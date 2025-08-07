from __future__ import annotations

"""Minimal post-process utility."""

from typing import Any, Dict, List, Tuple
import json
import os
from datetime import datetime
import pandas as pd
from schemas.template_v2 import PostprocessSpec, Template
from app_utils.dataframe_transform import apply_header_mappings
from app_utils.azure_sql import get_pit_url_payload


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
    process_guid: str,
    operation_cd: str | None = None,
    customer_name: str | None = None,
) -> Tuple[List[str], Dict[str, Any] | None]:
    """Run optional postprocess hooks based on ``template``."""

    logs: List[str] = []
    payload: Dict[str, Any] | None = None
    df = apply_header_mappings(df, template)
    if template.postprocess:
        if template.template_name == "PIT BID":
            if not operation_cd:
                raise ValueError("operation_cd required for PIT BID postprocess")
            if not process_guid:
                raise ValueError("process_guid required for PIT BID postprocess")
            logs.append(f"POST {template.postprocess.url}")
            payload = get_pit_url_payload(operation_cd)
            logs.append(f"Payload: {json.dumps(payload)}")
            if os.getenv("ENABLE_POSTPROCESS") == "1":
                now = datetime.utcnow()
                stamp = customer_name or now.strftime("%H%M%S")
                fname = f"{operation_cd} - {now.strftime('%Y%m%d')} PIT12wk - {stamp} BID.xlsm"
                item = payload.setdefault("item", {})
                in_data = item.setdefault("In_dtInputData", [{}])
                if not in_data:
                    in_data.append({})
                in_data[0]["NEW_EXCEL_FILENAME"] = fname
                payload["BID-Payload"] = process_guid
                logs.append(f"Payload: {json.dumps(payload)}")

                try:
                    import requests  # type: ignore

                    resp: requests.Response | None = requests.post(
                        template.postprocess.url, json=payload, timeout=10
                    )
                    if resp is not None:
                        logs.append(f"Status: {resp.status_code}")
                        logs.append(f"Body: {resp.text[:200]}")
                        resp.raise_for_status()
                    else:
                        logs.append("Status: no response")
                except Exception as exc:  # noqa: BLE001
                    logs.append(f"Error: {exc}")
                    raise
                else:
                    logs.append("Done")
            else:
                logs.append("Postprocess disabled")
        else:
            run_postprocess(template.postprocess, df, logs)
    return logs, payload
