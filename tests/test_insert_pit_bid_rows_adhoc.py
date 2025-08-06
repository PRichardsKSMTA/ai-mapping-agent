import pandas as pd
from app_utils import azure_sql


def _fake_conn(captured):
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

    return FakeConn()


def test_insert_pit_bid_rows_adhoc_sequential(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    df = pd.DataFrame(
        {
            "Lane ID": ["L1"],
            "Foo": ["x"],
            "Bar": ["y"],
            "Baz": ["z"],
        }
    )
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer")
    assert rows == 1
    params = captured["params"]
    assert params[2] == "L1"  # LANE_ID
    assert params[14] == "x"  # ADHOC_INFO1
    assert params[15] == "y"  # ADHOC_INFO2
    assert params[16] == "z"  # ADHOC_INFO3
    assert params[17] is None  # ADHOC_INFO4
    assert params[23] is None  # ADHOC_INFO10


def test_insert_pit_bid_rows_preserves_existing_adhoc(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    df = pd.DataFrame(
        {
            "Lane ID": ["L1"],
            "ADHOC_INFO1": ["keep"],
            "Extra": ["new"],
        }
    )
    rows = azure_sql.insert_pit_bid_rows(df, "OP", "Customer")
    assert rows == 1
    params = captured["params"]
    assert params[14] == "keep"  # existing ADHOC_INFO1 preserved
    assert params[15] == "new"  # ADHOC_INFO2 filled with extra column
    assert params[16] is None  # ADHOC_INFO3 remains None
    assert params[23] is None  # ADHOC_INFO10 remains None
