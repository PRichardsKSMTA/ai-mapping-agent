from __future__ import annotations

"""Helpers for Azure SQL queries."""

from typing import Any, Dict, List
import os
from pathlib import Path
from datetime import datetime
import re

import pandas as pd

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


def get_operational_scac(operation_cd: str) -> str:
    """Derive the operational SCAC from an operation code."""
    return operation_cd.split("_", 1)[0]


def insert_pit_bid_rows(
    df: pd.DataFrame,
    operation_cd: str,
    customer_name: str | None,
    process_guid: str | None = None,
) -> None:
    """Insert mapped ``pit-bid`` rows into ``dbo.RFP_OBJECT_DATA``.

    The DataFrame ``df`` is expected to already use pit-bid template field names.
    Each field is mapped explicitly to its target database column via
    ``field_map``. Columns that remain unmapped are stored sequentially in
    ``ADHOC_INFO1`` … ``ADHOC_INFO10``.
    """

    field_map: Dict[str, str] = {
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
        "Miles": "RFP_MILES",
        "Tolls": "FM_TOLLS",
        "Customer Name": "CUSTOMER_NAME",
        "Freight Type": "FREIGHT_TYPE",
        "Temp Cat": "TEMP_CAT",
        "BTF FSC Per Mile": "BTF_FSC_PER_MILE",
        "Volume Frequency": "VOLUME_FREQUENCY",
    }

    columns = [
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
    ] + [f"ADHOC_INFO{i}" for i in range(1, 11)] + [
        "RFP_MILES",
        "FM_TOLLS",
        "PROCESS_GUID",
        "INSERTED_DTTM",
        "VOLUME_FREQUENCY",
    ]
    placeholders = ",".join(["?"] * len(columns))
    now = datetime.utcnow()

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
    df_db = df.rename(columns=field_map).copy()
    if df_db.columns.duplicated().any():
        for col in df_db.columns[df_db.columns.duplicated()].unique():
            cols = [c for c in df_db.columns if c == col]
            df_db[col] = df_db[cols].bfill(axis=1).iloc[:, 0]
        df_db = df_db.loc[:, ~df_db.columns.duplicated()]

    conn = _connect()
    with conn:
        cur = conn.cursor()
        for _, row in df_db.iterrows():
            values = {c: None for c in columns}
            values["OPERATION_CD"] = operation_cd
            values["PROCESS_GUID"] = process_guid
            values["INSERTED_DTTM"] = now

            for col in df_db.columns:
                if col in columns:
                    if col == "CUSTOMER_NAME" and customer_name is not None:
                        continue
                    if col in float_fields:
                        values[col] = _to_float(row[col])
                    else:
                        values[col] = _to_str(row[col])

            if customer_name is not None:
                values["CUSTOMER_NAME"] = customer_name

            unmapped = [c for c in df_db.columns if c not in columns]
            for i, col in enumerate(unmapped[:10], start=1):
                values[f"ADHOC_INFO{i}"] = _to_str(row[col])

            cur.execute(
                f"INSERT INTO dbo.RFP_OBJECT_DATA ({','.join(columns)}) VALUES ({placeholders})",
                [values[c] for c in columns],
            )

