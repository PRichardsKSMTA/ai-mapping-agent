from __future__ import annotations

"""Helpers for Azure SQL queries."""

from typing import Any, Dict, List
import os
from pathlib import Path
from datetime import datetime
import re
import json
import logging

import pandas as pd

PIT_BID_FIELD_MAP: Dict[str, str] = {
    "Lane ID": "LANE_ID",
    "Origin City": "ORIG_CITY",
    "Orig State": "ORIG_ST",
    "Orig Zip (5 or 3)": "ORIG_POSTAL_CD",
    "Destination City": "DEST_CITY",
    "Dest State": "DEST_ST",
    "Dest Zip (5 or 3)": "DEST_POSTAL_CD",
    "Bid Volume": "BID_VOLUME",
    "LH Rate": "LH_RATE",
    "Bid Miles": "RFP_MILES",
    "Customer Name": "CUSTOMER_NAME",
    "Freight Type": "FREIGHT_TYPE",
    "Temp Cat": "TEMP_CAT",
    "BTF FSC Per Mile": "BTF_FSC_PER_MILE",
    "Volume Frequency": "VOLUME_FREQUENCY",
}

try:  # pragma: no cover - optional dependency
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - if python-dotenv not installed
    pass

try:  # pragma: no cover - handled in tests via monkeypatch
    import tomllib  # Python 3.11+
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore

try:  # pragma: no cover - handled in tests via monkeypatch
    import pyodbc  # type: ignore
except Exception:  # pragma: no cover - if pyodbc missing or misconfigured
    pyodbc = None  # type: ignore


def _load_secret(key: str) -> str | None:
    """Return a config value from env or `.streamlit/secrets.toml`."""
    if val := os.getenv(key):
        return val
    secrets_path = Path(".streamlit") / "secrets.toml"
    if tomllib and secrets_path.exists():  # pragma: no cover - executed in app
        with secrets_path.open("rb") as fh:
            secrets = tomllib.load(fh)
        raw = secrets.get(key)
        return str(raw) if raw is not None else None
    return None


def _build_conn_str() -> str:
    """Assemble an ODBC connection string from config."""
    server = _load_secret("SQL_SERVER")
    database = _load_secret("SQL_DATABASE")
    username = _load_secret("SQL_USERNAME")
    password = _load_secret("SQL_PASSWORD")
    if not all([server, database, username, password]):
        raise RuntimeError(
            "SQL connection is not configured; set SQL_SERVER, SQL_DATABASE, "
            "SQL_USERNAME, and SQL_PASSWORD"
        )
    return (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={server};DATABASE={database};UID={username};PWD={password}"
    )


def _connect() -> "pyodbc.Connection":
    """Return a database connection or raise ``RuntimeError`` if misconfigured."""
    if not pyodbc:
        raise RuntimeError("pyodbc is not installed")
    conn_str = os.getenv("AZURE_SQL_CONN_STRING") or _build_conn_str()
    return pyodbc.connect(conn_str)


def fetch_operation_codes(email: str | None = None) -> List[str]:
    """Return sorted operation codes for a user email.

    Falls back to the demo user when ``email`` is ``None``.
    """
    email = email or os.getenv("DEV_USER_EMAIL", "pete.richards@ksmta.com")
    try:
        conn = _connect()
    except RuntimeError as err:  # pragma: no cover - exercised in integration
        raise RuntimeError(f"Operation code lookup failed: {err}") from err
    with conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT OPERATION_CD FROM dbo.V_O365_MEMBER_OPERATIONS WHERE EMAIL = ? AND OPERATION_CD NOT LIKE '%LOG'",
            email,
        )
        rows = cur.fetchall()
    return sorted(row[0] for row in rows)


def fetch_customers(operational_scac: str) -> List[Dict[str, str]]:
    """Return customer records for a given operational SCAC."""
    try:
        conn = _connect()
    except RuntimeError as err:  # pragma: no cover - exercised in integration
        raise RuntimeError(f"Customer lookup failed: {err}") from err
    with conn:
        cur = conn.cursor()
        cur.execute(
            (
                "SELECT CLIENT_SCAC, BILLTO_ID, BILLTO_NAME, BILLTO_TYPE, OPERATIONAL_SCAC "
                "FROM dbo.V_SPOQ_BILLTOS WHERE OPERATIONAL_SCAC = ?"
            ),
            operational_scac,
        )
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return sorted(rows, key=lambda r: r["BILLTO_NAME"])


def fetch_freight_type(operation_cd: str) -> str | None:
    """Return the default freight type for an operation code."""
    try:
        conn = _connect()
    except RuntimeError as err:  # pragma: no cover - exercised in integration
        raise RuntimeError(f"Freight type lookup failed: {err}") from err
    with conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT TOP 1 FREIGHT_TYPE FROM dbo.V_OPERATION_FREIGHT_TYPE WHERE OPERATION_CD = ?",
            operation_cd,
        )
        row = cur.fetchone()
    return row[0] if row else None


def get_pit_url_payload(op_cd: str, week_ct: int = 12) -> Dict[str, Any]:
    """Return the PIT URL JSON payload for an operation code."""
    try:
        conn = _connect()
    except RuntimeError as err:  # pragma: no cover - exercised in integration
        raise RuntimeError(f"PIT URL payload lookup failed: {err}") from err
    with conn:
        cur = conn.cursor()
        cur.execute("SELECT dbo.GetPITURLPayload(?, ?)", op_cd, week_ct)
        row = cur.fetchone()
    if not row or row[0] == "null":
        msg = f"PIT URL payload missing for {op_cd}"
        logging.error(msg)
        raise RuntimeError(msg)
    raw = row[0]
    return json.loads(raw)


def get_operational_scac(operation_cd: str) -> str:
    """Derive the operational SCAC from an operation code."""
    return operation_cd.split("_", 1)[0]


def derive_adhoc_headers(df: pd.DataFrame) -> Dict[str, str]:
    """Return mapping of ``ADHOC_INFO`` slots to original column headers."""

    base_columns = [
        "OPERATION_CD",
        "CUSTOMER_NAME",
        "LANE_ID",
        "ORIG_CITY",
        "ORIG_ST",
        "ORIG_POSTAL_CD",
        "DEST_CITY",
        "DEST_ST",
        "DEST_POSTAL_CD",
        "BID_VOLUME",
        "LH_RATE",
        "FREIGHT_TYPE",
        "TEMP_CAT",
        "BTF_FSC_PER_MILE",
    ]
    adhoc_slots = [f"ADHOC_INFO{i}" for i in range(1, 11)]
    tail_columns = [
        "RFP_MILES",
        "FM_TOLLS",
        "PROCESS_GUID",
        "INSERTED_DTTM",
        "VOLUME_FREQUENCY",
    ]

    df_db = df.rename(columns=PIT_BID_FIELD_MAP).copy()
    if df_db.columns.duplicated().any():
        for col in df_db.columns[df_db.columns.duplicated()].unique():
            cols = [c for c in df_db.columns if c == col]
            df_db[col] = df_db[cols].bfill(axis=1).iloc[:, 0]
        df_db = df_db.loc[:, ~df_db.columns.duplicated()]

    try:  # pragma: no cover - optional DB call
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'dbo' "
                "AND TABLE_NAME = 'RFP_OBJECT_DATA'"
            )
            db_columns = {row[0] for row in cur.fetchall()}
    except Exception:  # pragma: no cover - DB unavailable
        db_columns = set()

    extra_columns = [
        col
        for col in df_db.columns
        if col in db_columns
        and col not in base_columns
        and col not in tail_columns
        and col not in adhoc_slots
    ]
    columns = base_columns + extra_columns + adhoc_slots + tail_columns
    values = {c: None for c in columns}
    unmapped = [c for c in df_db.columns if c not in values]
    available_slots = [slot for slot in adhoc_slots if values[slot] is None]
    return {slot: col for slot, col in zip(available_slots, unmapped)}


def insert_pit_bid_rows(
    df: pd.DataFrame,
    operation_cd: str,
    customer_name: str,
    process_guid: str | None = None,
    adhoc_headers: Dict[str, str] | None = None,
    *,
    batch_size: int = 1000,
    tvp_name: str | None = None,
    use_bulk_insert: bool = False,
) -> int:
    """Insert mapped ``pit-bid`` rows into ``dbo.RFP_OBJECT_DATA``.

    The DataFrame ``df`` is expected to already use pit-bid template field names.
    Each field is mapped explicitly to its target database column via
    ``PIT_BID_FIELD_MAP``. Columns that remain unmapped are stored sequentially
    in ``ADHOC_INFO1`` … ``ADHOC_INFO10``.
    ``customer_name`` is required and applied to every inserted row regardless
    of any ``CUSTOMER_NAME`` column in ``df``. ``adhoc_headers`` maps
    ``ADHOC_INFO`` slot names to their source column headers. It is currently
    unused but accepted so callers can persist the mapping via
    :func:`log_mapping_process`.
    """

    base_columns = [
        "OPERATION_CD",
        "CUSTOMER_NAME",
        "LANE_ID",
        "ORIG_CITY",
        "ORIG_ST",
        "ORIG_POSTAL_CD",
        "DEST_CITY",
        "DEST_ST",
        "DEST_POSTAL_CD",
        "BID_VOLUME",
        "LH_RATE",
        "FREIGHT_TYPE",
        "TEMP_CAT",
        "BTF_FSC_PER_MILE",
    ]
    adhoc_slots = [f"ADHOC_INFO{i}" for i in range(1, 11)]
    tail_columns = [
        "RFP_MILES",
        "FM_TOLLS",
        "PROCESS_GUID",
        "INSERTED_DTTM",
        "VOLUME_FREQUENCY",
    ]
    float_fields = {
        "BID_VOLUME",
        "LH_RATE",
        "BTF_FSC_PER_MILE",
        "RFP_MILES",
        "FM_TOLLS",
    }

    def _to_float(val: Any) -> float | None:
        if pd.isna(val) or val == "":
            return None
        if isinstance(val, str):
            txt = val.strip()
            if txt.startswith("(") and txt.endswith(")"):
                txt = "-" + txt[1:-1]
            txt = re.sub(r"[^0-9.+-]", "", txt)
            if txt in {"", ".", "+", "-", "+.", "-."}:
                return None
            try:
                return float(txt)
            except ValueError:
                return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    def _to_str(val: Any) -> str | None:
        if pd.isna(val):
            return None
        text = str(val).strip()
        return text or None

    df_db = df.rename(columns=PIT_BID_FIELD_MAP).copy()
    if df_db.columns.duplicated().any():
        for col in df_db.columns[df_db.columns.duplicated()].unique():
            cols = [c for c in df_db.columns if c == col]
            df_db[col] = df_db[cols].bfill(axis=1).iloc[:, 0]
        df_db = df_db.loc[:, ~df_db.columns.duplicated()]

    default_freight = None
    if "FREIGHT_TYPE" not in df_db.columns or df_db["FREIGHT_TYPE"].isna().all():
        default_freight = fetch_freight_type(operation_cd)

    conn = _connect()
    with conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'dbo' "
            "AND TABLE_NAME = 'RFP_OBJECT_DATA'",
        )
        db_columns = {row[0] for row in cur.fetchall()}
        extra_columns = [
            col
            for col in df_db.columns
            if col in db_columns
            and col not in base_columns
            and col not in tail_columns
            and col not in adhoc_slots
        ]
        columns = base_columns + extra_columns + adhoc_slots + tail_columns

        unmapped = [
            c
            for c in df_db.columns
            if c not in base_columns
            and c not in extra_columns
            and c not in adhoc_slots
            and c not in tail_columns
        ]
        available_slots = [slot for slot in adhoc_slots if slot not in df_db.columns]
        for slot, col in zip(available_slots, unmapped):
            df_db[slot] = df_db[col]

        for col in df_db.columns.intersection(float_fields):
            df_db[col] = df_db[col].map(_to_float)
        for col in df_db.columns.difference(float_fields):
            df_db[col] = df_db[col].map(_to_str)

        now = datetime.utcnow()
        df_db = df_db.reindex(columns=columns).astype(object)
        df_db = df_db.where(pd.notna(df_db), None)
        df_db["OPERATION_CD"] = operation_cd
        df_db["CUSTOMER_NAME"] = customer_name
        df_db["PROCESS_GUID"] = process_guid
        df_db["INSERTED_DTTM"] = now
        if default_freight is not None:
            df_db["FREIGHT_TYPE"] = df_db["FREIGHT_TYPE"].fillna(default_freight)

        rows = list(df_db.itertuples(index=False, name=None))
        if not rows:
            return 0

        cur.fast_executemany = True  # type: ignore[attr-defined]
        placeholders = ",".join(["?"] * len(columns))
        if tvp_name and pyodbc and hasattr(pyodbc, "TableValuedParam"):
            tvp = pyodbc.TableValuedParam(tvp_name, rows)  # type: ignore[attr-defined]
            cur.execute(
                f"INSERT INTO dbo.RFP_OBJECT_DATA ({','.join(columns)}) SELECT * FROM ?",
                tvp,
            )
        elif use_bulk_insert:
            import csv
            import tempfile

            with tempfile.NamedTemporaryFile("w", newline="", delete=False) as tmp:
                csv.writer(tmp).writerows(rows)
                tmp_path = tmp.name
            try:
                cur.execute(
                    f"BULK INSERT dbo.RFP_OBJECT_DATA FROM '{tmp_path}' WITH (FORMAT = 'CSV')"
                )
            finally:
                os.unlink(tmp_path)
        else:
            query = (
                f"INSERT INTO dbo.RFP_OBJECT_DATA ({','.join(columns)}) VALUES ({placeholders})"
            )
            for start in range(0, len(rows), batch_size):
                batch = rows[start : start + batch_size]
                cur.executemany(query, batch)
    return len(rows)


def log_mapping_process(
    process_guid: str,
    template_name: str,
    friendly_name: str,
    created_by: str,
    file_name_string: str,
    process_json: dict | str,
    template_guid: str,
    adhoc_headers: Dict[str, str] | None = None,
) -> None:
    """Insert a record into ``dbo.MAPPING_AGENT_PROCESSES``."""
    payload = (
        json.loads(process_json) if isinstance(process_json, str) else dict(process_json)
    )
    if adhoc_headers:
        payload["adhoc_headers"] = adhoc_headers
    with _connect() as conn:
        conn.cursor().execute(
            "INSERT INTO dbo.MAPPING_AGENT_PROCESSES (PROCESS_GUID, TEMPLATE_NAME, FRIENDLY_NAME, CREATED_BY, CREATED_DTTM, FILE_NAME_STRING, PROCESS_JSON, TEMPLATE_GUID) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                process_guid,
                template_name,
                friendly_name,
                created_by,
                datetime.utcnow(),
                file_name_string,
                json.dumps(payload),
                template_guid,
            ),
        )
