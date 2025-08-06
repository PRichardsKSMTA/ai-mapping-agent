import types
import pytest
import pandas as pd

from app_utils import azure_sql


def test_get_operational_scac():
    assert azure_sql.get_operational_scac("ADSJ_VAN") == "ADSJ"
    assert azure_sql.get_operational_scac("ABC12_FLT") == "ABC12"


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


def test_insert_pit_bid_rows(monkeypatch):
    captured = {}

    class FakeCursor:
        def execute(self, query, params):  # pragma: no cover - executed via call
            captured["query"] = query
            captured["params"] = params

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    monkeypatch.setattr(azure_sql, "_connect", lambda: FakeConn())
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
            "Tolls": [7],
            "Foo": ["bar"],
        }
    )
    azure_sql.insert_pit_bid_rows(df, "OP", "Customer", "guid")
    assert "RFP_OBJECT_DATA" in captured["query"]
    assert captured["params"][0] == "OP"
    assert captured["params"][1] == "Customer"
    assert captured["params"][2] == "L1"
    assert captured["params"][14] == "bar"  # ADHOC_INFO1
    assert captured["params"][24] == 100  # RFP_MILES
    assert captured["params"][28] is None  # VOLUME_FREQUENCY
    assert len(captured["params"]) == 29


def test_insert_pit_bid_rows_blanks(monkeypatch):
    captured = {}

    class FakeCursor:
        def execute(self, query, params):  # pragma: no cover - executed via call
            captured["params"] = params

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    monkeypatch.setattr(azure_sql, "_connect", lambda: FakeConn())
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
            "Tolls": [""],
        }
    )
    azure_sql.insert_pit_bid_rows(df, "OP", "Customer", "guid")
    assert captured["params"][9] is None  # BID_VOLUME
    assert captured["params"][10] is None  # LH_RATE
    assert captured["params"][24] is None  # RFP_MILES
    assert captured["params"][25] is None  # RFP_TOLLS


def test_insert_pit_bid_rows_aliases(monkeypatch):
    captured = {}

    class FakeCursor:
        def execute(self, query, params):  # pragma: no cover - executed via call
            captured["params"] = params

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    monkeypatch.setattr(azure_sql, "_connect", lambda: FakeConn())
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
            "Miles": [123],
        }
    )
    azure_sql.insert_pit_bid_rows(df, "OP", "Customer")
    assert captured["params"][2] == "L1"
    assert captured["params"][24] == 123


def test_insert_pit_bid_rows_customer_column(monkeypatch):
    captured = {}

    class FakeCursor:
        def execute(self, query, params):  # pragma: no cover - executed via call
            captured["params"] = params

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    monkeypatch.setattr(azure_sql, "_connect", lambda: FakeConn())
    df = pd.DataFrame(
        {
            "Customer Name": ["Cust1"],
            "Lane ID": ["L1"],
            "Origin City": ["OC"],
            "Orig State": ["OS"],
        }
    )
    azure_sql.insert_pit_bid_rows(df, "OP", None)
    assert captured["params"][1] == "Cust1"
