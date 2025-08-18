from __future__ import annotations

"""Helpers for Azure SQL queries."""

from typing import Any, Dict, List, Sequence, Tuple
import os
from pathlib import Path
from datetime import datetime
import time
import re
import json
import logging

import pandas as pd
from .state_abbrev import abbreviate_state

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
    "Breakthrough Fuel": "BTF_FSC_PER_MILE",
    "Volume Frequency": "VOLUME_FREQUENCY",
}

FREIGHT_TYPE_MAP: Dict[str, str] = {
    "V": "V",
    "VAN": "V",
    "R": "R",
    "REEFER": "R",
    "F": "F",
    "FLATBED": "F",
    "D": "D",
    "DEDICATED": "D",
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


def _normalize_host_port(server_value: str) -> Tuple[str, int]:
    """
    Accepts forms like:
      'tcp:myserver.database.windows.net'
      'tcp:myserver.database.windows.net,1433'
      'myserver.database.windows.net'
      'myserver.database.windows.net,1433'
    Returns (host, port).
    """
    v = (server_value or "").strip()
    if v.lower().startswith("tcp:"):
        v = v[4:]
    if "," in v:
        host, port_s = v.split(",", 1)
        try:
            port = int(port_s)
        except Exception:
            port = 1433
    else:
        host, port = v, 1433
    return host, port


def _build_conn_str() -> str:
    """Assemble an ODBC connection string for Microsoft ODBC Driver 18."""
    # Support both your existing SQL_* keys and AZURE_SQL_* synonyms.
    server = _load_secret("SQL_SERVER") or _load_secret("AZURE_SQL_SERVER")
    database = _load_secret("SQL_DATABASE") or _load_secret("AZURE_SQL_DB")
    username = _load_secret("SQL_USERNAME") or _load_secret("AZURE_SQL_USER")
    password = _load_secret("SQL_PASSWORD") or _load_secret("AZURE_SQL_PASSWORD")
    if not all([server, database, username, password]):
        raise RuntimeError(
            "SQL connection is not configured; set SQL_SERVER/SQL_DATABASE/"
            "SQL_USERNAME/SQL_PASSWORD (or AZURE_SQL_SERVER/AZURE_SQL_DB/"
            "AZURE_SQL_USER/AZURE_SQL_PASSWORD)"
        )
    return (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={server};DATABASE={database};UID={username};PWD={password};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )


def _odbc_diag_log() -> None:
    import logging
    try:
        import pyodbc
        logging.info("Available ODBC drivers: %s", pyodbc.drivers())
    except Exception as exc:
        logging.error("pyodbc not importable: %s", exc)


def _build_conn_str_msodbc(driver_name: str) -> str:
    """Build a connection string for the given Microsoft ODBC driver name (17 or 18)."""
    server = _load_secret("SQL_SERVER") or _load_secret("AZURE_SQL_SERVER")
    database = _load_secret("SQL_DATABASE") or _load_secret("AZURE_SQL_DB")
    username = _load_secret("SQL_USERNAME") or _load_secret("AZURE_SQL_USER")
    password = _load_secret("SQL_PASSWORD") or _load_secret("AZURE_SQL_PASSWORD")
    if not all([server, database, username, password]):
        raise RuntimeError(
            "SQL connection is not configured; set SQL_SERVER/SQL_DATABASE/"
            "SQL_USERNAME/SQL_PASSWORD (or AZURE_SQL_SERVER/AZURE_SQL_DB/"
            "AZURE_SQL_USER/AZURE_SQL_PASSWORD)"
        )
    return (
        f"DRIVER={{{driver_name}}};"
        f"SERVER={server};DATABASE={database};UID={username};PWD={password};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )



def _freetds_lib_candidates() -> List[str]:
    # Try common locations for libtdsodbc.so on Debian/Ubuntu images
    return [
        "/usr/lib/x86_64-linux-gnu/odbc/libtdsodbc.so",
        "/usr/lib/arm64-linux-gnu/odbc/libtdsodbc.so",
        "/usr/lib/aarch64-linux-gnu/odbc/libtdsodbc.so",
        "/usr/lib64/libtdsodbc.so",
        "/usr/local/lib/libtdsodbc.so",
    ]


def _build_conn_str_freetds_path(lib_path: str) -> str:
    server = _load_secret("SQL_SERVER") or _load_secret("AZURE_SQL_SERVER")
    database = _load_secret("SQL_DATABASE") or _load_secret("AZURE_SQL_DB")
    username = _load_secret("SQL_USERNAME") or _load_secret("AZURE_SQL_USER")
    password = _load_secret("SQL_PASSWORD") or _load_secret("AZURE_SQL_PASSWORD")
    if not all([server, database, username, password]):
        raise RuntimeError(
            "SQL connection is not configured; set SQL_SERVER/SQL_DATABASE/"
            "SQL_USERNAME/SQL_PASSWORD (or AZURE_SQL_SERVER/AZURE_SQL_DB/"
            "AZURE_SQL_USER/AZURE_SQL_PASSWORD)"
        )
    host, port = _normalize_host_port(server)
    return (
        f"Driver={lib_path};"
        f"Server={host};Port={port};Database={database};"
        f"UID={username};PWD={password};"
        "TDS_Version=7.4;Encrypt=yes;TrustServerCertificate=no;"
        "ClientCharset=UTF-8;Connection Timeout=30;"
    )


def _connect() -> "pyodbc.Connection":
    """Return a DB connection using Microsoft ODBC 18 or 17. No FreeTDS fallback."""
    try:
        import pyodbc  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pyodbc import failed") from exc

    # Explicit connection string still wins if you provide one.
    user_conn_str = os.getenv("AZURE_SQL_CONN_STRING")
    if user_conn_str:
        return pyodbc.connect(user_conn_str)

    # Probe available ODBC drivers and pick the best Microsoft one.
    drivers = getattr(pyodbc, "drivers", lambda: [])()
    drivers_lower = [d.lower() for d in drivers]
    if "odbc driver 18 for sql server" in drivers_lower:
        driver_name = "ODBC Driver 18 for SQL Server"
    elif "odbc driver 17 for sql server" in drivers_lower:
        driver_name = "ODBC Driver 17 for SQL Server"
    else:
        raise RuntimeError(
            "Microsoft ODBC Driver 17/18 for SQL Server not found in this environment. "
            "On Streamlit Cloud, v17 is typically preinstalled. If needed, add 'msodbcsql17' "
            "to packages.txt. Available drivers: " + repr(drivers)
        )

    return pyodbc.connect(_build_conn_str_msodbc(driver_name))

    
def _pyodbc_driver_name(conn) -> str:
    try:
        import pyodbc
        return (conn.getinfo(pyodbc.SQL_DRIVER_NAME) or "").lower()
    except Exception:
        return ""

def _is_ms_odbc(conn) -> bool:
    name = _pyodbc_driver_name(conn)
    # msodbcsqlXX.so on Linux; SQLNCLI*.DLL on older Windows clients
    return ("msodbc" in name) or ("sqlncli" in name) or ("odbc" in name and "sql" in name and "ms" in name)

def _is_freetds(conn) -> bool:
    return "tdsodbc" in _pyodbc_driver_name(conn)


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
            "SELECT OPERATION_CD FROM dbo.V_O365_MEMBER_OPERATIONS WHERE EMAIL = ? AND PIT_REFRESH = 1",
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
        rows: List[Dict[str, str]] = []
        for raw in cur.fetchall():
            row = dict(zip(cols, raw))
            name = row.get("BILLTO_NAME")
            if isinstance(name, str):
                row["BILLTO_NAME"] = name.strip().title()
            else:
                row["BILLTO_NAME"] = ""
            rows.append(row)
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
            "SELECT FREIGHT_TYPE FROM dbo.CLIENT_OPERATION_CODES WHERE OPERATION_CD = ?",
            operation_cd,
        )
        row = cur.fetchone()
    if not row:
        return None
    freight: str = row[0]
    return str(freight).strip().upper()


def wait_for_postprocess_completion(
    process_guid: str,
    operation_cd: str,
    poll_interval: int = 30,
    max_attempts: int = 2,
) -> None:
    """Poll ``dbo.MAPPING_AGENT_PROCESSES`` until postprocess is complete.

    Executes ``dbo.RFP_OBJECT_DATA_POST_PROCESS`` and then checks
    ``POST_PROCESS_COMPLETE_DTTM`` every ``poll_interval`` seconds. After
    ten polls (5 minutes with the default 30-second interval) without a
    completion timestamp, the stored procedure is invoked again. The cycle
    repeats until ``max_attempts`` is reached. The connection is committed
    after each poll so subsequent ``SELECT`` statements read freshly
    committed data.
    """
    logger = logging.getLogger(__name__)
    checks_per_attempt = 10
    with _connect() as conn:
        cur = conn.cursor()
        for attempt in range(max_attempts):
            logger.info(
                "Executing RFP_OBJECT_DATA_POST_PROCESS for %s / %s (attempt %s/%s)",
                operation_cd,
                process_guid,
                attempt + 1,
                max_attempts,
            )
            cur.execute(
                "EXEC dbo.RFP_OBJECT_DATA_POST_PROCESS ?, ?, NULL",
                process_guid,
                operation_cd,
            )
            conn.commit()
            for _ in range(checks_per_attempt):
                logger.info("Sleeping %s seconds before next poll", poll_interval)
                time.sleep(poll_interval)
                cur.execute(
                    "SELECT POST_PROCESS_COMPLETE_DTTM FROM dbo.MAPPING_AGENT_PROCESSES WHERE PROCESS_GUID = ?",
                    process_guid,
                )
                row = cur.fetchone()
                conn.commit()
                logger.debug("Committed transaction to start a new polling transaction")
                complete = row[0] if row else None
                if complete is not None:
                    logger.info(
                        "Post-process complete for %s at %s", process_guid, complete
                    )
                    return
            if attempt < max_attempts - 1:
                logger.info(
                    "Re-running postprocess after %s seconds of polling",
                    poll_interval * checks_per_attempt,
                )
        logger.warning(
            "Post-process did not complete for %s after %s attempts",
            process_guid,
            max_attempts,
        )


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
        "CUSTOMER_ID",
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
    if "CUSTOMER_ID" in df_db.columns:
        df_db = df_db.drop(columns=["CUSTOMER_ID"])
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
    customer_ids: Sequence[str] | None = None,
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
    of any ``CUSTOMER_NAME`` column in ``df``. ``customer_ids`` may be ``None``
    or contain up to five entries. If ``customer_ids`` is ``None`` or an empty
    sequence, ``CUSTOMER_ID`` is inserted as ``NULL``. ``adhoc_headers`` maps
    ``ADHOC_INFO`` slot names to their source column headers. It is currently
    unused but accepted so callers can persist the mapping via
    :func:`log_mapping_process`.
    """
    base_columns = [
        "OPERATION_CD",
        "CUSTOMER_NAME",
        "CUSTOMER_ID",
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

    def _prep_state(val: Any, field: str) -> str | None:
        if pd.isna(val) or val == "":
            return None
        text = str(val).strip()
        abbr = abbreviate_state(text)
        if abbr:
            return abbr
        if len(text) >= 2:
            return text[:2].upper()
        raise ValueError(f"{field} value '{val}' cannot be abbreviated")
    if "Lane ID" not in df.columns or df["Lane ID"].isna().all():
        df = df.copy()
        df["Lane ID"] = range(1, len(df) + 1)

    df_db = df.rename(columns=PIT_BID_FIELD_MAP).copy()
    if "CUSTOMER_ID" in df_db.columns:
        df_db = df_db.drop(columns=["CUSTOMER_ID"])
    if df_db.columns.duplicated().any():
        for col in df_db.columns[df_db.columns.duplicated()].unique():
            cols = [c for c in df_db.columns if c == col]
            df_db[col] = df_db[cols].bfill(axis=1).iloc[:, 0]
        df_db = df_db.loc[:, ~df_db.columns.duplicated()]

    if "LANE_ID" not in df_db.columns or df_db["LANE_ID"].isna().any():
        raise ValueError("LANE_ID cannot be null")

    for col in ["ORIG_ST", "DEST_ST"]:
        if col in df_db.columns:
            df_db[col] = df_db[col].apply(lambda v, c=col: _prep_state(v, c))

    default_freight = None
    if "FREIGHT_TYPE" in df_db.columns:
        df_db["FREIGHT_TYPE"] = df_db["FREIGHT_TYPE"].map(
            lambda v: FREIGHT_TYPE_MAP.get(str(v).strip().upper())
            if v is not None
            else None,
        )
        if df_db["FREIGHT_TYPE"].isna().all():
            default_freight = fetch_freight_type(operation_cd)
    else:
        default_freight = fetch_freight_type(operation_cd)

    ids = list(customer_ids or [])
    if len(ids) > 5:
        raise ValueError("Up to 5 customer IDs supported")

    conn = _connect()
    with conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT COLUMN_NAME, CHARACTER_MAXIMUM_LENGTH FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'RFP_OBJECT_DATA'",
        )
        info_rows = cur.fetchall()
        char_max = {row[0]: row[1] for row in info_rows}
        db_columns = char_max.keys()
        extra_columns = [
            col
            for col in df_db.columns
            if col in db_columns
            and col not in base_columns
            and col not in tail_columns
            and col not in adhoc_slots
        ]
        columns = base_columns + extra_columns + adhoc_slots + tail_columns

        transform_start = time.perf_counter()
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
        df_db["CUSTOMER_ID"] = ",".join(ids) if ids else None
        df_db["PROCESS_GUID"] = process_guid
        df_db["INSERTED_DTTM"] = now
        if default_freight is not None:
            df_db["FREIGHT_TYPE"] = df_db.get("FREIGHT_TYPE", pd.Series([None] * len(df_db)))
            df_db["FREIGHT_TYPE"] = df_db["FREIGHT_TYPE"].fillna(default_freight)

        for col, max_len in char_max.items():
            if max_len is None or max_len < 0 or col not in df_db.columns:
                continue
            mask = df_db[col].notna()
            if not mask.any():
                continue
            too_long = df_db.loc[mask, col].map(lambda v: len(v) > max_len)
            if too_long.any():
                bad_val = df_db.loc[mask, col][too_long].iloc[0]
                raise ValueError(
                    f"{col} value '{bad_val}' exceeds max length {max_len}"
                )

        rows = list(df_db.itertuples(index=False, name=None))
        transform_time = time.perf_counter() - transform_start
        if not rows:
            logging.info(
                "insert_pit_bid_rows transform=%.3fs db=0.000s", transform_time
            )
            return 0

        try:
            # Re-enable fast_executemany on Microsoft ODBC
            cur.fast_executemany = True  # type: ignore[attr-defined]
            placeholders = ",".join(["?"] * len(columns))
            db_start = time.perf_counter()
            try:  # pragma: no cover - handled in tests via monkeypatch
                import pyodbc as _pyodbc  # type: ignore
            except Exception:  # pragma: no cover - if pyodbc missing
                _pyodbc = None  # type: ignore
            if tvp_name and _pyodbc and hasattr(_pyodbc, "TableValuedParam"):
                tvp = _pyodbc.TableValuedParam(tvp_name, rows)  # type: ignore[attr-defined]
                cur.execute(
                    f"INSERT INTO dbo.RFP_OBJECT_DATA ({','.join(columns)}) SELECT * FROM ?",
                    tvp,
                )
            elif use_bulk_insert:
                # (optional path you had; fine to leave in)
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
            db_time = time.perf_counter() - db_start

        except Exception as err:
            raise RuntimeError(f"Failed to insert PIT bid rows: {err}") from err
    logging.info(
        "insert_pit_bid_rows transform=%.3fs db=%.3fs", transform_time, db_time
    )
    return len(rows)


def log_mapping_process(
    process_guid: str,
    operation_cd: str | None,
    template_name: str,
    friendly_name: str,
    created_by: str,
    file_name_string: str,
    process_json: dict | str,
    template_guid: str,
    adhoc_headers: Dict[str, str] | None = None,
) -> None:
    """Insert a record into ``dbo.MAPPING_AGENT_PROCESSES``.

    ``operation_cd`` is optional and may be ``None``.
    """
    payload = (
        json.loads(process_json) if isinstance(process_json, str) else dict(process_json)
    )
    if adhoc_headers:
        payload["adhoc_headers"] = adhoc_headers
    with _connect() as conn:
        conn.cursor().execute(
            "INSERT INTO dbo.MAPPING_AGENT_PROCESSES (PROCESS_GUID, OPERATION_CD, TEMPLATE_NAME, FRIENDLY_NAME, CREATED_BY, CREATED_DTTM, FILE_NAME_STRING, PROCESS_JSON, TEMPLATE_GUID) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                process_guid,
                operation_cd,
                template_name,
                friendly_name,
                created_by,
                datetime.utcnow(),
                file_name_string,
                json.dumps(payload),
                template_guid,
            ),
        )
