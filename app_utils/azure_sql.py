from __future__ import annotations

"""Helpers for Azure SQL queries."""

from typing import Dict, List, Optional
import os

try:  # pragma: no cover - handled in tests via monkeypatch
    import pyodbc  # type: ignore
except Exception:  # pragma: no cover - if pyodbc missing or misconfigured
    pyodbc = None  # type: ignore


def _connect() -> Optional["pyodbc.Connection"]:
    """Return a database connection if configured."""
    conn_str = os.getenv("AZURE_SQL_CONN_STRING")
    if not conn_str or not pyodbc:
        return None
    return pyodbc.connect(conn_str)


def fetch_operation_codes(email: str) -> List[str]:
    """Return sorted operation codes for a user email."""
    conn = _connect()
    if not conn:
        return []
    with conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT OPERATION_CD FROM dbo.V_O365_MEMBER_OPERATIONS WHERE EMAIL = ?",
            email,
        )
        rows = cur.fetchall()
    return sorted(row[0] for row in rows)


def fetch_customers(operational_scac: str) -> List[Dict[str, str]]:
    """Return customer records for a given operational SCAC."""
    conn = _connect()
    if not conn:
        return []
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
