import pandas as pd
from app_utils import azure_sql


def _fake_conn(captured, columns: dict[str, int | None] | None = None):
    class FakeCursor:
        def __init__(self) -> None:
            self.columns: dict[str, int | None] = dict(columns or {})
            self.fast_executemany = False

        def execute(self, query, params=None):  # pragma: no cover - executed via call
            if "INFORMATION_SCHEMA.COLUMNS" in query:
                return self
            captured["params"] = params
            return self

        def executemany(self, query, params):  # pragma: no cover - executed via call
            captured.setdefault("batches", []).append(list(params))
            captured["params"] = params[0] if params else None
            captured["fast_executemany"] = self.fast_executemany
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


def test_insert_pit_bid_rows_leaves_adhoc_blank_without_mapping(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: None)
    df = pd.DataFrame(
        {
            "Lane ID": ["L1"],
            "Foo": ["x"],
            "Bar": ["y"],
            "Baz": ["z"],
        }
    )
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer", ["1"])
    assert rows == 1
    params = captured["params"]
    assert params[3] == "L1"  # LANE_ID
    assert params[15] is None  # ADHOC_INFO1 remains blank without manual mapping
    assert params[16] is None  # ADHOC_INFO2 remains blank without manual mapping
    assert params[17] is None  # ADHOC_INFO3 remains blank without manual mapping
    assert params[18] is None  # ADHOC_INFO4 remains blank without manual mapping
    assert params[24] is None  # ADHOC_INFO10 remains blank without manual mapping


def test_insert_pit_bid_rows_preserves_manual_adhoc(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: None)
    df = pd.DataFrame(
        {
            "Lane ID": ["L1"],
            "ADHOC_INFO1": ["keep"],
            "Extra": ["new"],
        }
    )
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer", ["1"])
    assert rows == 1
    params = captured["params"]
    assert params[15] == "keep"  # existing ADHOC_INFO1 preserved
    assert params[16] is None  # ADHOC_INFO2 not auto-filled by extra column
    assert params[17] is None  # ADHOC_INFO3 remains None
    assert params[24] is None  # ADHOC_INFO10 remains None


def test_insert_pit_bid_rows_batches(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    monkeypatch.setattr(azure_sql, "fetch_freight_type", lambda op: None)
    df = pd.DataFrame({
        "Lane ID": [f"L{i}" for i in range(1500)],
        "Foo": [i for i in range(1500)],
    })
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer", ["1"], batch_size=1000)
    assert rows == 1500
    assert len(captured["batches"]) == 2
    assert len(captured["batches"][0]) == 1000
    assert len(captured["batches"][1]) == 500
