from __future__ import annotations

"""Minimal post-process utility."""

from typing import Any, Dict, List, Tuple
import json
import logging
import pandas as pd
from schemas.template_v2 import PostprocessSpec, Template
from app_utils.dataframe_transform import apply_header_mappings
from app_utils.azure_sql import get_pit_url_payload, wait_for_postprocess_completion


def run_postprocess(
    cfg: PostprocessSpec, df: pd.DataFrame, log: List[str] | None = None
) -> None:
    """Send mapped data to ``cfg.url`` via HTTP POST."""
    if log is not None:
        log.append("POST request sent")
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
    customer_name: str,
    operation_cd: str | None = None,
    poll_interval: int = 30,
) -> Tuple[List[str], Dict[str, Any] | List[Dict[str, Any]] | None]:
    """Run optional postprocess hooks based on ``template``."""

    logs: List[str] = []
    payload: Dict[str, Any] | List[Dict[str, Any]] | None = None
    df = apply_header_mappings(df, template)
    if not template.postprocess:
        return logs, payload
    if template.template_name == "PIT BID":
        if not operation_cd:
            raise ValueError("operation_cd required for PIT BID postprocess")
        if not process_guid:
            raise ValueError("process_guid required for PIT BID postprocess")
        class _ListHandler(logging.Handler):
            def __init__(self, buf: List[str]) -> None:
                super().__init__()
                self.buf = buf

            def emit(self, record: logging.LogRecord) -> None:
                self.buf.append(record.getMessage())

        handler = _ListHandler(logs)
        logger = logging.getLogger("app_utils.azure_sql")
        logger.addHandler(handler)
        old_level = logger.level
        logger.setLevel(logging.INFO)
        try:
            wait_for_postprocess_completion(
                process_guid, operation_cd, poll_interval=poll_interval
            )
        finally:
            logger.removeHandler(handler)
            logger.setLevel(old_level)
        logs.append("POST request sent")
        try:
            payload = get_pit_url_payload(operation_cd)
        except RuntimeError as err:  # pragma: no cover - exercised in integration
            logs.append(f"Payload error: {err}")
            raise
<<<<<<< HEAD
        payload["DEST_FOLDER_PATH"] = "/Client Downloads/Pricing Tools"
=======
        dest_path: str = "/Client Downloads/Pricing Tools/Customer Bids"
        payload["CLIENT_DEST_FOLDER_PATH"] = dest_path
>>>>>>> 4654018593263a31a57780746684da85bab849d6
        logs.append("Payload loaded")
        fname = f"{operation_cd} - BID - {customer_name}.xlsm"
        payload.setdefault("item/In_dtInputData", [{}])
        if not payload["item/In_dtInputData"]:
            payload["item/In_dtInputData"].append({})
        payload["item/In_dtInputData"][0]["NEW_EXCEL_FILENAME"] = fname
        for entry in payload.get("item/In_dtInputData", []):
            entry["CLIENT_DEST_FOLDER_PATH"] = dest_path
        if "BID-Payload" in payload:
            payload["BID-Payload"] = process_guid
        else:
            logs.append("Missing BID-Payload in payload")
        logs.append("Payload finalized")
        try:
            import requests  # type: ignore

            resp: requests.Response | None = requests.post(
                template.postprocess.url, json=payload, timeout=10
            )
            if resp is not None:
                logs.append(f"Status: {resp.status_code}")
                resp.raise_for_status()
            else:
                logs.append("Status: no response")
        except Exception as exc:  # noqa: BLE001
            logs.append(f"Error: {exc}")
            raise
        else:
            logs.append("Done")
    else:
        payload = df.to_dict(orient="records")
        run_postprocess(template.postprocess, df, logs)
    return logs, payload
