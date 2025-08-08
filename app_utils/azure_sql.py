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


def insert_pit_bid_rows(
    df: pd.DataFrame,
    operation_cd: str,
    customer_name: str | None,
    process_guid: str | None = None,
    ) -> int:
    """Insert mapped ``pit-bid`` rows into ``dbo.RFP_OBJECT_DATA``.

    The DataFrame ``df`` is expected to already use pit-bid template field names.
    Each field is mapped explicitly to its target database column via
    ``PIT_BID_FIELD_MAP``. Columns that remain unmapped are stored sequentially
    in ``ADHOC_INFO1`` … ``ADHOC_INFO10``.
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


    # Rename DataFrame columns to their target database names.
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
            "AND TABLE_NAME = 'RFP_OBJECT_DATA'"
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
        placeholders = ",".join(["?"] * len(columns))
        now = datetime.utcnow()
        rows: list[list[Any]] = []
        for _, row in df_db.iterrows():
            values = {c: None for c in columns}
            values["OPERATION_CD"] = operation_cd
            values["PROCESS_GUID"] = process_guid
            values["INSERTED_DTTM"] = now
            for col in df_db.columns:
                if col in values:
                    if col == "CUSTOMER_NAME" and customer_name is not None:
                        continue
                    if col in float_fields:
                        values[col] = _to_float(row[col])
                    else:
                        values[col] = _to_str(row[col])
            if customer_name is not None:
                values["CUSTOMER_NAME"] = customer_name
            if values["FREIGHT_TYPE"] is None:
                values["FREIGHT_TYPE"] = default_freight
            unmapped = [c for c in df_db.columns if c not in values]
            available_slots = [slot for slot in adhoc_slots if values[slot] is None]
            for slot, col in zip(available_slots, unmapped):
                values[slot] = _to_str(row[col])
            rows.append([values[c] for c in columns])
        if rows:
            cur.fast_executemany = True  # type: ignore[attr-defined]
            cur.executemany(
                f"INSERT INTO dbo.RFP_OBJECT_DATA ({','.join(columns)}) VALUES ({placeholders})",
                rows,
            )
    return len(rows)


def log_mapping_process(process_guid: str, template_name: str, friendly_name: str,
                        created_by: str, file_name_string: str,
                        process_json: dict | str, template_guid: str) -> None:
    """Insert a record into ``dbo.MAPPING_AGENT_PROCESSES``."""
    with _connect() as conn:
        conn.cursor().execute(
            "INSERT INTO dbo.MAPPING_AGENT_PROCESSES (PROCESS_GUID, TEMPLATE_NAME, FRIENDLY_NAME, CREATED_BY, CREATED_DTTM, FILE_NAME_STRING, PROCESS_JSON, TEMPLATE_GUID) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (process_guid, template_name, friendly_name, created_by, datetime.utcnow(), file_name_string,
             json.dumps(process_json) if not isinstance(process_json, str) else process_json, template_guid),
        )
