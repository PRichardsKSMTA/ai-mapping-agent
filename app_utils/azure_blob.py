from __future__ import annotations
import os
import io
import mimetypes
import re
from datetime import datetime, date
from typing import BinaryIO, Dict, Optional, Union

from azure.storage.blob import BlobServiceClient, ContentSettings
import streamlit as st

# Optional .env support
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

def _get(name: str, default: Optional[str] = None) -> Optional[str]:
    # prefer env; fall back to Streamlit secrets if present
    val = os.environ.get(name)
    if val is not None:
        return val
    try:
        return st.secrets.get(name, default)  # type: ignore[attr-defined]
    except Exception:
        return default

def _blob_service_client() -> BlobServiceClient:
    conn_str = _get("AZURE_STORAGE_CONNECTION_STRING")
    if conn_str:
        return BlobServiceClient.from_connection_string(conn_str)

    account_url = _get("AZURE_BLOB_ACCOUNT_URL")
    sas = _get("AZURE_BLOB_SAS")
    if account_url and sas:
        return BlobServiceClient(account_url=account_url, credential=sas)

    raise RuntimeError(
        "Blob Storage not configured. Provide AZURE_STORAGE_CONNECTION_STRING "
        "or AZURE_BLOB_ACCOUNT_URL + AZURE_BLOB_SAS."
    )

def _sanitize_filename(name: str) -> str:
    name = name.strip().replace("\\", "/").split("/")[-1]
    # allow letters, numbers, dot, dash, underscore
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name or "upload.bin"

def _guess_content_type(filename: str) -> str:
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"

def upload_fileobj(
    fileobj: BinaryIO | bytes,
    *,
    blob_path: str,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> str:
    """
    Stream 'fileobj' to Azure Blob at 'blob_path' inside the configured container.
    Returns the HTTPS blob URL (no SAS appended).
    """
    container = _get("AZURE_BLOB_CONTAINER", "rfp-files") or "rfp-files"
    svc = _blob_service_client()
    container_client = svc.get_container_client(container)
    try:
        container_client.create_container()  # idempotent if it exists
    except Exception:
        pass

    blob_client = container_client.get_blob_client(blob_path)
    data_stream = fileobj if hasattr(fileobj, "read") else io.BytesIO(fileobj)
    ct = content_type or _guess_content_type(blob_path)
    blob_client.upload_blob(
        data_stream,
        overwrite=True,  # safe because our path is date/filename; adjust if you want immutability
        content_settings=ContentSettings(content_type=ct),
        metadata=metadata or {},
    )
    return f"{blob_client.url}"

def build_rfp_blob_path(
    *,
    operation_cd: str,
    original_filename: str,
    for_date: Optional[Union[date, datetime]] = None,
) -> str:
    """
    New path convention (container is configured separately):
      <OPERATION_CD>/<YYYY-MM-DD>/<filename>

    Example (effective URL):
      https://<acct>.blob.core.windows.net/rfp-files/ADSJ_VAN/2025-11-18/filename.xlsx
    """
    if not operation_cd:
        raise ValueError("operation_cd is required for path building")

    op = re.sub(r"[^A-Za-z0-9._-]+", "_", str(operation_cd).strip()).upper() or "UNKNOWN"
    d = for_date.date() if isinstance(for_date, datetime) else (for_date or date.today())
    ymd = d.strftime("%Y-%m-%d")
    base = _sanitize_filename(original_filename)
    return f"{op}/{ymd}/{base}"
