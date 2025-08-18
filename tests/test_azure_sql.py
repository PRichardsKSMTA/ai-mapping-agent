import builtins
import logging
import sys
import types

import pandas as pd
import pytest

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
        "Breakthrough Fuel": "BTF_FSC_PER_MILE",
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

    monkeypatch.setattr(azure_sql, "_connect", lambda: FakeConn())

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

    monkeypatch.setattr(azure_sql, "_connect", lambda: FakeConn())
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

    monkeypatch.setattr(azure_sql, "_connect", lambda: FakeConn())

    customers = azure_sql.fetch_customers("ADSJ")
    assert [c["BILLTO_NAME"] for c in customers] == ["Alpha", "Beta"]
def test_connect_requires_config(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pyodbc":
            return types.SimpleNamespace(connect=lambda conn_str: None)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
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


def test_connect_import_error(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pyodbc":
            raise ImportError("boom")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError) as exc:
        azure_sql._connect()
    assert "pyodbc import failed" in str(exc.value)
    assert isinstance(exc.value.__cause__, ImportError)


def _fake_conn(captured: dict, columns: dict[str, int | None] | None = None):
    class FakeCursor:
        def __init__(self) -> None:
            base_cols = {"FREIGHT_TYPE": 1}
            base_cols.update(columns or {})
            self.columns = base_cols
            self.fast_executemany = False

        def execute(self, query, params=None):  # pragma: no cover - executed via call
            if "INFORMATION_SCHEMA.COLUMNS" in query:
                return self
            captured["query"] = query
            captured["params"] = params
            return self

        def executemany(self, query, params):  # pragma: no cover - executed via call
            captured["query"] = query
            captured.setdefault("batches", []).append(list(params))
            captured["params"] = params[0] if params else None
            captured["fast_executemany"] = self.fast_executemany
            if self.columns and "INSERT INTO" in query:
                cols = query.split("(")[1].split(")", 1)[0].split(",")
                cols = [c.strip() for c in cols]
                for row in params:
                    for col, max_len in self.columns.items():
                        if max_len is not None and max_len > 0:
                            idx = cols.index(col)
                            val = row[idx]
                            if val is not None and len(str(val)) > max_len:
                                raise Exception(f"{col} value exceeds length {max_len}")
            return self

        def fetchall(self):  # pragma: no cover - executed via call
            return list(self.columns.items())

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
    customer_ids = ["1", "2"]
    rows = azure_sql.insert_pit_bid_rows(
        df, "OP", "Customer", customer_ids, "guid", {"ADHOC_INFO1": "Foo"}
    )
    assert rows == 1
    assert "RFP_OBJECT_DATA" in captured["query"]
    assert captured["params"][0] == "OP"
    assert captured["params"][1] == "Customer"
    assert captured["params"][2] == ",".join(customer_ids)
    assert captured["params"][3] == "L1"
    assert captured["params"][6] == "11111"  # ORIG_POSTAL_CD
    assert captured["params"][9] == "22222"  # DEST_POSTAL_CD
    assert captured["params"][10] == 5  # BID_VOLUME
    assert captured["params"][11] == 1.2  # LH_RATE
    assert captured["params"][15] == "bar"  # ADHOC_INFO1
    assert captured["params"][25] == 100  # RFP_MILES
    assert captured["params"][26] is None  # FM_TOLLS
    assert captured["params"][29] is None  # VOLUME_FREQUENCY
    assert len(captured["params"]) == 30


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
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer", ["1"], "guid")
    assert rows == 1
    assert captured["params"][10] is None  # BID_VOLUME
    assert captured["params"][11] is None  # LH_RATE
    assert captured["params"][25] is None  # RFP_MILES


def test_insert_pit_bid_rows_no_ids(monkeypatch):
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
        }
    )
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer", None, "guid")
    assert rows == 1
    assert captured["params"][2] is None  # CUSTOMER_ID


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
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer", ["1"])
    assert rows == 1
    assert captured["params"][3] == "L1"
    assert captured["params"][25] == 123
    assert captured["params"][15] is None  # no ADHOC columns


def test_insert_pit_bid_rows_autofill_freight_type(monkeypatch):
    captured = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: "V")
    df = pd.DataFrame({"Lane ID": ["L1"]})
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer", ["1"])
    assert rows == 1
    assert captured["params"][12] == "V"


def test_insert_pit_bid_rows_generates_lane_ids(monkeypatch):
    captured = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: None)
    df = pd.DataFrame({"Origin City": ["OC1", "OC2"]})
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer", ["1"])
    assert rows == 2
    lane_ids = [row[3] for row in captured["batches"][0]]
    assert lane_ids == ["1", "2"]


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
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer", ["1"])
    assert rows == 1
    assert captured["params"][6] == "01111"
    assert captured["params"][9] == "02222"
    assert captured["params"][10] == 5000.0
    assert captured["params"][11] == 1.5
    assert captured["params"][25] == 1234.0


def test_insert_pit_bid_rows_length_error(monkeypatch):
    captured = {}
    cols = {"LANE_ID": 5}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured, cols))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: None)
    df = pd.DataFrame({"Lane ID": ["123456"]})
    with pytest.raises(ValueError) as exc:
        azure_sql.insert_pit_bid_rows(df, "OP", "Customer", ["1"])
    assert "LANE_ID" in str(exc.value)


def test_insert_pit_bid_rows_nvarchar_max(monkeypatch):
    captured = {}
    cols = {"ADHOC_INFO1": -1}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured, cols))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: None)
    long_val = "x" * 5000
    df = pd.DataFrame({"Lane ID": ["L1"], "Foo": [long_val]})
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer", ["1"])
    assert rows == 1
    assert captured["params"][15] == long_val

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
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer", ["1"])
    assert rows == 1
    assert captured["params"][1] == "Customer"


def test_insert_pit_bid_rows_customer_id_column_ignored(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: None)
    df = pd.DataFrame({"Lane ID": ["L1"], "CUSTOMER_ID": ["OLD"]})
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer", ["NEW"])
    assert rows == 1
    assert captured["params"][2] == "NEW"
    assert captured["params"][15] is None  # ADHOC_INFO1 remains empty


def test_insert_pit_bid_rows_customer_id_cap(monkeypatch):
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn({}))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: None)
    df = pd.DataFrame({"Lane ID": ["L1"]})
    ids = [str(i) for i in range(6)]
    with pytest.raises(ValueError):
        azure_sql.insert_pit_bid_rows(df, "OP", "Customer", ids)


def test_insert_pit_bid_rows_freight_type_van(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: None)
    df = pd.DataFrame({"Lane ID": ["L1"], "FREIGHT_TYPE": ["VAN"]})
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer", ["1"])
    assert rows == 1
    assert captured["params"][12] == "V"  # FREIGHT_TYPE


def test_insert_pit_bid_rows_invalid_freight_type_uses_default(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: "R")
    df = pd.DataFrame({"Lane ID": ["L1"], "FREIGHT_TYPE": ["plane"]})
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer", ["1"])
    assert rows == 1
    assert captured["params"][12] == "R"  # FREIGHT_TYPE


def test_insert_pit_bid_rows_unmapped_no_alias(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    df = pd.DataFrame(
        {
            "CUSTOMER": ["Acme"],
            "Freight Type": ["van"],
            "Foo": ["bar"],
        }
    )
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer", ["1"])
    assert rows == 1
    assert captured["params"][1] == "Customer"  # CUSTOMER_NAME
    assert captured["params"][12] == "V"  # FREIGHT_TYPE
    assert captured["params"][15] == "Acme"  # ADHOC_INFO1
    assert captured["params"][16] == "bar"  # ADHOC_INFO2


def test_insert_pit_bid_rows_extends_known_columns(monkeypatch):
    captured = {}
    table_cols = {"EXTRA_COL": None}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured, table_cols))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: None)
    monkeypatch.setitem(azure_sql.PIT_BID_FIELD_MAP, "Extra Field", "EXTRA_COL")
    df = pd.DataFrame({"Lane ID": ["L1"], "Extra Field": ["val"]})
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer", ["1"])
    assert rows == 1
    assert captured["params"][15] == "val"  # EXTRA_COL
    assert captured["params"][16] is None  # ADHOC_INFO1 unused
    assert len(captured["params"]) == 31


def test_insert_pit_bid_rows_unknown_columns_to_adhoc(monkeypatch):
    captured = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: None)
    monkeypatch.setitem(azure_sql.PIT_BID_FIELD_MAP, "Extra Field", "MISSING_COL")
    df = pd.DataFrame({"Lane ID": ["L1"], "Extra Field": ["val"]})
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer", ["1"])
    assert rows == 1
    assert captured["params"][15] == "val"  # ADHOC_INFO1
    assert len(captured["params"]) == 30


def test_insert_pit_bid_rows_batches(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: None)
    df = pd.DataFrame({"Lane ID": [f"L{i}" for i in range(1500)]})
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer", ["1"], batch_size=1000)
    assert rows == 1500
    assert len(captured["batches"]) == 2
    assert len(captured["batches"][0]) == 1000
    assert len(captured["batches"][1]) == 500


def test_insert_pit_bid_rows_tvp(monkeypatch):
    captured: dict = {}

    class FakeTVP:
        def __init__(self, name, rows):
            self.name = name
            self.rows = rows

    fake_pyodbc = types.SimpleNamespace(TableValuedParam=FakeTVP)
    monkeypatch.setitem(sys.modules, "pyodbc", fake_pyodbc)
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: None)
    df = pd.DataFrame({"Lane ID": ["L1", "L2"]})
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer", ["1"], tvp_name="dbo.TVP")
    assert rows == 2
    assert isinstance(captured["params"], FakeTVP)
    assert captured["params"].name == "dbo.TVP"


def test_insert_pit_bid_rows_logs(monkeypatch, caplog):
    captured: dict = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: None)
    df = pd.DataFrame({"Lane ID": ["L1"]})

    class FakeTime:
        def __init__(self) -> None:
            self.times = iter([0.0, 1.0, 1.0, 3.0])

        def perf_counter(self) -> float:
            return next(self.times)

    monkeypatch.setattr(azure_sql, "time", FakeTime())
    with caplog.at_level(logging.INFO):
        azure_sql.insert_pit_bid_rows(df, "OP", "Customer", ["1"])
    assert any("transform=1.000s" in m and "db=2.000s" in m for m in caplog.messages)

