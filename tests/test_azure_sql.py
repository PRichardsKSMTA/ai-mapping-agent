import types
import pytest
import pandas as pd

from app_utils import azure_sql


def test_get_operational_scac():
    assert azure_sql.get_operational_scac("ADSJ_VAN") == "ADSJ"
    assert azure_sql.get_operational_scac("ABC12_FLT") == "ABC12"


def test_pit_bid_field_map_alignment():
    expected = {
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
    assert azure_sql.PIT_BID_FIELD_MAP == expected


def test_fetch_operation_codes(monkeypatch):
    class FakeCursor:
        def execute(self, query, email):  # pragma: no cover - exercised via call
            assert "FROM dbo.V_O365_MEMBER_OPERATIONS" in query
            assert email == "user@example.com"
            self.description = [("OPERATION_CD",)]
            self.rows = [("DEK1_REF",), ("ADSJ_VAN",)]
            return self

        def fetchall(self):
            return self.rows

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    fake_pyodbc = types.SimpleNamespace(connect=lambda conn_str: FakeConn())
    monkeypatch.setattr(azure_sql, "pyodbc", fake_pyodbc)
    monkeypatch.setenv("SQL_SERVER", "srv")
    monkeypatch.setenv("SQL_DATABASE", "db")
    monkeypatch.setenv("SQL_USERNAME", "user")
    monkeypatch.setenv("SQL_PASSWORD", "pwd")

    codes = azure_sql.fetch_operation_codes("user@example.com")
    assert codes == ["ADSJ_VAN", "DEK1_REF"]


def test_fetch_operation_codes_default_email(monkeypatch):
    class FakeCursor:
        def execute(self, query, email):  # pragma: no cover - exercised via call
            assert email == "pete.richards@ksmta.com"
            self.description = [("OPERATION_CD",)]
            self.rows = [("DEK1_REF",)]
            return self

        def fetchall(self):
            return self.rows

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    fake_pyodbc = types.SimpleNamespace(connect=lambda conn_str: FakeConn())
    monkeypatch.setattr(azure_sql, "pyodbc", fake_pyodbc)
    monkeypatch.setenv("SQL_SERVER", "srv")
    monkeypatch.setenv("SQL_DATABASE", "db")
    monkeypatch.setenv("SQL_USERNAME", "user")
    monkeypatch.setenv("SQL_PASSWORD", "pwd")
    monkeypatch.delenv("DEV_USER_EMAIL", raising=False)

    codes = azure_sql.fetch_operation_codes()
    assert codes == ["DEK1_REF"]


def test_fetch_customers(monkeypatch):
    class FakeCursor:
        def execute(self, query, scac):  # pragma: no cover - exercised via call
            assert "FROM dbo.V_SPOQ_BILLTOS" in query
            assert scac == "ADSJ"
            self.description = [
                ("CLIENT_SCAC",),
                ("BILLTO_ID",),
                ("BILLTO_NAME",),
                ("BILLTO_TYPE",),
                ("OPERATIONAL_SCAC",),
            ]
            self.rows = [
                ("ADSJ", "1", "Beta", "T", "ADSJ"),
                ("ADSJ", "2", "Alpha", "T", "ADSJ"),
            ]
            return self

        def fetchall(self):
            return self.rows

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    fake_pyodbc = types.SimpleNamespace(connect=lambda conn_str: FakeConn())
    monkeypatch.setattr(azure_sql, "pyodbc", fake_pyodbc)
    monkeypatch.setenv("SQL_SERVER", "srv")
    monkeypatch.setenv("SQL_DATABASE", "db")
    monkeypatch.setenv("SQL_USERNAME", "user")
    monkeypatch.setenv("SQL_PASSWORD", "pwd")

    customers = azure_sql.fetch_customers("ADSJ")
    assert [c["BILLTO_NAME"] for c in customers] == ["Alpha", "Beta"]


def test_connect_requires_config(monkeypatch):
    monkeypatch.setattr(azure_sql, "pyodbc", types.SimpleNamespace())
    for key in [
        "SQL_SERVER",
        "SQL_DATABASE",
        "SQL_USERNAME",
        "SQL_PASSWORD",
        "AZURE_SQL_CONN_STRING",
    ]:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(RuntimeError):
        azure_sql._connect()


def test_connect_requires_pyodbc(monkeypatch):
    monkeypatch.setattr(azure_sql, "pyodbc", None)
    monkeypatch.setenv("SQL_SERVER", "srv")
    monkeypatch.setenv("SQL_DATABASE", "db")
    monkeypatch.setenv("SQL_USERNAME", "user")
    monkeypatch.setenv("SQL_PASSWORD", "pwd")
    with pytest.raises(RuntimeError):
        azure_sql._connect()


def _fake_conn(captured: dict, columns: set[str] | None = None):
    class FakeCursor:
        def __init__(self) -> None:
            self.columns = list(columns or [])
            self.fast_executemany = False

        def execute(self, query, params=None):  # pragma: no cover - executed via call
            if "INFORMATION_SCHEMA.COLUMNS" in query:
                return self
            captured["query"] = query
            captured["params"] = params
            return self

        def executemany(self, query, params):  # pragma: no cover - executed via call
            captured["query"] = query
            captured["params"] = params[0] if params else None
            return self

        def fetchall(self):  # pragma: no cover - executed via call
            return [(c,) for c in self.columns]

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    return FakeConn()


def test_insert_pit_bid_rows(monkeypatch):
    captured = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: None)
    df = pd.DataFrame(
        {
            "Lane ID": ["L1"],
            "Origin City": ["OC"],
            "Orig State": ["OS"],
            "Orig Zip (5 or 3)": ["11111"],
            "Destination City": ["DC"],
            "Dest State": ["DS"],
            "Dest Zip (5 or 3)": ["22222"],
            "Bid Volume": [5],
            "LH Rate": [1.2],
            "Bid Miles": [100],
            "Foo": ["bar"],
        }
    )
    rows = azure_sql.insert_pit_bid_rows(
        df, "OP", "Customer", "guid", {"ADHOC_INFO1": "Foo"}
    )
    assert rows == 1
    assert "RFP_OBJECT_DATA" in captured["query"]
    assert captured["params"][0] == "OP"
    assert captured["params"][1] == "Customer"
    assert captured["params"][2] == "L1"
    assert captured["params"][5] == "11111"  # ORIG_POSTAL_CD
    assert captured["params"][8] == "22222"  # DEST_POSTAL_CD
    assert captured["params"][9] == 5  # BID_VOLUME
    assert captured["params"][10] == 1.2  # LH_RATE
    assert captured["params"][14] == "bar"  # ADHOC_INFO1
    assert captured["params"][24] == 100  # RFP_MILES
    assert captured["params"][25] is None  # FM_TOLLS
    assert captured["params"][28] is None  # VOLUME_FREQUENCY
    assert len(captured["params"]) == 29


def test_insert_pit_bid_rows_blanks(monkeypatch):
    captured = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: None)
    df = pd.DataFrame(
        {
            "Lane ID": ["L1"],
            "Origin City": ["OC"],
            "Orig State": ["OS"],
            "Orig Zip (5 or 3)": ["11111"],
            "Destination City": ["DC"],
            "Dest State": ["DS"],
            "Dest Zip (5 or 3)": ["22222"],
            "Bid Volume": [""],
            "LH Rate": [""],
            "Bid Miles": [""],
        }
    )
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer", "guid")
    assert rows == 1
    assert captured["params"][9] is None  # BID_VOLUME
    assert captured["params"][10] is None  # LH_RATE
    assert captured["params"][24] is None  # RFP_MILES


def test_insert_pit_bid_rows_with_db_columns(monkeypatch):
    captured = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: None)
    df = pd.DataFrame(
        {
            "LANE_ID": ["L1"],
            "ORIG_CITY": ["OC"],
            "ORIG_ST": ["OS"],
            "ORIG_POSTAL_CD": ["11111"],
            "DEST_CITY": ["DC"],
            "DEST_ST": ["DS"],
            "DEST_POSTAL_CD": ["22222"],
            "BID_VOLUME": [5],
            "LH_RATE": [1.2],
            "RFP_MILES": [123],
        }
    )
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer")
    assert rows == 1
    assert captured["params"][2] == "L1"
    assert captured["params"][24] == 123
    assert captured["params"][14] is None  # no ADHOC columns


def test_insert_pit_bid_rows_autofill_freight_type(monkeypatch):
    captured = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: "LTL")
    df = pd.DataFrame({"Lane ID": ["L1"]})
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer")
    assert rows == 1
    assert captured["params"][11] == "LTL"


def test_insert_pit_bid_rows_formatted_numbers(monkeypatch):
    captured = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: None)
    df = pd.DataFrame(
        {
            "Lane ID": ["L1"],
            "Orig Zip (5 or 3)": ["01111"],
            "Dest Zip (5 or 3)": ["02222"],
            "Bid Volume": ["5,000"],
            "LH Rate": ["$1.50"],
            "Bid Miles": ["1,234"],
        }
    )
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer")
    assert rows == 1
    assert captured["params"][5] == "01111"
    assert captured["params"][8] == "02222"
    assert captured["params"][9] == 5000.0
    assert captured["params"][10] == 1.5
    assert captured["params"][24] == 1234.0

def test_insert_pit_bid_rows_customer_column_ignored(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: None)
    df = pd.DataFrame(
        {
            "Customer Name": ["Cust1"],
            "Lane ID": ["L1"],
            "Origin City": ["OC"],
            "Orig State": ["OS"],
        }
    )
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer")
    assert rows == 1
    assert captured["params"][1] == "Customer"


def test_insert_pit_bid_rows_unmapped_no_alias(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    df = pd.DataFrame(
        {
            "CUSTOMER": ["Acme"],
            "Freight Type": ["TL"],
            "Foo": ["bar"],
        }
    )
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer")
    assert rows == 1
    assert captured["params"][1] == "Customer"  # CUSTOMER_NAME
    assert captured["params"][11] == "TL"  # FREIGHT_TYPE
    assert captured["params"][14] == "Acme"  # ADHOC_INFO1
    assert captured["params"][15] == "bar"  # ADHOC_INFO2


def test_insert_pit_bid_rows_extends_known_columns(monkeypatch):
    captured = {}
    table_cols = {"EXTRA_COL"}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured, table_cols))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: None)
    monkeypatch.setitem(azure_sql.PIT_BID_FIELD_MAP, "Extra Field", "EXTRA_COL")
    df = pd.DataFrame({"Lane ID": ["L1"], "Extra Field": ["val"]})
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer")
    assert rows == 1
    assert captured["params"][14] == "val"  # EXTRA_COL
    assert captured["params"][15] is None  # ADHOC_INFO1 unused
    assert len(captured["params"]) == 30


def test_insert_pit_bid_rows_unknown_columns_to_adhoc(monkeypatch):
    captured = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: None)
    monkeypatch.setitem(azure_sql.PIT_BID_FIELD_MAP, "Extra Field", "MISSING_COL")
    df = pd.DataFrame({"Lane ID": ["L1"], "Extra Field": ["val"]})
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer")
    assert rows == 1
    assert captured["params"][14] == "val"  # ADHOC_INFO1
    assert len(captured["params"]) == 29

