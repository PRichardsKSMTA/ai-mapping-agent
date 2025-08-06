from __future__ import annotations

"""Helpers for Azure SQL queries."""

from typing import Any, Dict, List
import os
from pathlib import Path
from datetime import datetime

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
    customer_name: str,
    process_guid: str | None = None,
) -> None:
    """Insert mapped ``pit-bid`` rows into ``dbo.RFP_OBJECT_DATA``.

    Unknown or unused columns are stored sequentially in ``ADHOC_INFO1`` …
    ``ADHOC_INFO10``. Remaining optional fields are left ``NULL``.
    """

    field_specs = [
        ("LANE_ID", ["Lane ID", "LANE_ID"]),
        ("ORIG_CITY", ["Origin City", "ORIG_CITY"]),
        ("ORIG_ST", ["Orig State", "ORIG_ST"]),
        (
            "ORIG_POSTAL_CD",
            ["Orig Zip (5 or 3)", "ORIG_POSTAL_CD"],
        ),
        ("DEST_CITY", ["Destination City", "DEST_CITY"]),
        ("DEST_ST", ["Dest State", "DEST_ST"]),
        (
            "DEST_POSTAL_CD",
            ["Dest Zip (5 or 3)", "DEST_POSTAL_CD"],
        ),
        ("BID_VOLUME", ["Bid Volume", "BID_VOLUME"]),
        ("LH_RATE", ["LH Rate", "LH_RATE"]),
    ]
    known = {src for _, srcs in field_specs for src in srcs}
    known |= {"Bid Miles", "Miles", "Tolls"}
    customer_col = None
    if customer_name is None:
        for cand in ("Customer Name", "CUSTOMER_NAME"):
            if cand in df.columns:
                customer_col = cand
                known.add(cand)
                break
    extra_cols = [c for c in df.columns if c not in known]
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
        "RFP_TOLLS",
        "PROCESS_GUID",
        "INSERTED_DTTM",
        "VOLUME_FREQUENCY",
    ]
    placeholders = ",".join(["?"] * len(columns))
    now = datetime.utcnow()

    def _to_float(val: Any) -> float | None:
        if pd.isna(val) or val == "":
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

    conn = _connect()
    with conn:
        cur = conn.cursor()
        for _, row in df.iterrows():
            base_vals: List[Any] = []
            for dest, srcs in field_specs:
                val = None
                for src in srcs:
                    val = row.get(src)
                    if val not in (None, "") and not pd.isna(val):
                        break
                if dest in {"BID_VOLUME", "LH_RATE"}:
                    base_vals.append(_to_float(val))
                else:
                    base_vals.append(_to_str(val))
            adhoc_vals = [_to_str(row.get(col)) for col in extra_cols][:10]
            adhoc_vals.extend([None] * (10 - len(adhoc_vals)))
            miles_val = row.get("Bid Miles")
            if miles_val in (None, "") or pd.isna(miles_val):
                miles_val = row.get("Miles")
            cust_val = customer_name
            if cust_val is None and customer_col:
                cust_val = _to_str(row.get(customer_col))
            values = (
                [operation_cd, cust_val]
                + base_vals
                + [None, None, None]
                + adhoc_vals
                + [
                    _to_float(miles_val),
                    _to_float(row.get("Tolls")),
                    process_guid,
                    now,
                    None,
                ]
            )
            cur.execute(
                f"INSERT INTO dbo.RFP_OBJECT_DATA ({','.join(columns)}) VALUES ({placeholders})",
                values,
            )

