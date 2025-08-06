from __future__ import annotations

"""Helpers for Azure SQL queries."""

from typing import Any, Dict, List
import os
from pathlib import Path
from datetime import datetime
import re
import difflib

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

    Columns in ``df`` that match (directly or loosely) existing database column
    names are inserted into those columns. Remaining unmapped fields are stored
    sequentially in ``ADHOC_INFO1`` … ``ADHOC_INFO10``.
    """

    field_aliases: Dict[str, List[str]] = {
        "LANE_ID": ["Lane ID", "LANE_ID"],
        "ORIG_CITY": ["Origin City", "ORIG_CITY"],
        "ORIG_ST": ["Orig State", "ORIG_ST"],
        "ORIG_POSTAL_CD": ["Orig Zip (5 or 3)", "ORIG_POSTAL_CD"],
        "DEST_CITY": ["Destination City", "DEST_CITY"],
        "DEST_ST": ["Dest State", "DEST_ST"],
        "DEST_POSTAL_CD": ["Dest Zip (5 or 3)", "DEST_POSTAL_CD"],
        "BID_VOLUME": ["Bid Volume", "BID_VOLUME"],
        "LH_RATE": ["LH Rate", "LH_RATE"],
        "RFP_MILES": ["Bid Miles", "Miles", "RFP Miles", "RFP_MILES"],
        "RFP_TOLLS": ["Tolls", "RFP Tolls", "RFP_TOLLS"],
        "CUSTOMER_NAME": [
            "Customer Name",
            "Customer",
            "customer",
            "CUSTOMER",
            "CUSTOMER_NAME",
        ],
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

    float_fields = {"BID_VOLUME", "LH_RATE", "BTF_FSC_PER_MILE", "RFP_MILES", "RFP_TOLLS"}

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

    def _norm(name: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", name.upper())

    def _fuzzy_match(name: str, choices: List[str]) -> str | None:
        norm_name = _norm(name)
        best: tuple[str | None, float] = (None, 0.0)
        for cand in choices:
            ratio = difflib.SequenceMatcher(None, norm_name, _norm(cand)).ratio()
            if ratio > best[1]:
                best = (cand, ratio)
        return best[0] if best[1] >= 0.8 else None

    mapped_sources: Dict[str, str] = {}
    known: set[str] = set()

    for dest, aliases in field_aliases.items():
        for alias in aliases:
            if alias in df.columns:
                mapped_sources[dest] = alias
                known.add(alias)
                break

    # override customer_name if provided, otherwise try fuzzy match
    if customer_name is not None:
        mapped_sources.pop("CUSTOMER_NAME", None)
    elif "CUSTOMER_NAME" not in mapped_sources:
        if match := _fuzzy_match("CUSTOMER_NAME", list(df.columns)):
            mapped_sources["CUSTOMER_NAME"] = match
            known.add(match)

    dest_candidates = [
        c
        for c in columns
        if not c.startswith("ADHOC_INFO")
        and c not in {"OPERATION_CD", "PROCESS_GUID", "INSERTED_DTTM"}
        and c not in mapped_sources
    ]

    for col in df.columns:
        if col in known:
            continue
        if match := _fuzzy_match(col, dest_candidates):
            mapped_sources[match] = col
            known.add(col)
            dest_candidates.remove(match)

    adhoc_cols = [c for c in df.columns if c not in known]

    conn = _connect()
    with conn:
        cur = conn.cursor()
        for _, row in df.iterrows():
            values = {c: None for c in columns}
            values["OPERATION_CD"] = operation_cd
            values["PROCESS_GUID"] = process_guid
            values["INSERTED_DTTM"] = now
            if customer_name is not None:
                values["CUSTOMER_NAME"] = customer_name

            for dest, src in mapped_sources.items():
                if dest == "CUSTOMER_NAME" and customer_name is not None:
                    continue
                val = row.get(src)
                if dest in float_fields:
                    values[dest] = _to_float(val)
                else:
                    values[dest] = _to_str(val)

            if customer_name is None and "CUSTOMER_NAME" in mapped_sources:
                values["CUSTOMER_NAME"] = _to_str(row.get(mapped_sources["CUSTOMER_NAME"]))

            for i, col in enumerate(adhoc_cols[:10], start=1):
                values[f"ADHOC_INFO{i}"] = _to_str(row.get(col))

            cur.execute(
                f"INSERT INTO dbo.RFP_OBJECT_DATA ({','.join(columns)}) VALUES ({placeholders})",
                [values[c] for c in columns],
            )

