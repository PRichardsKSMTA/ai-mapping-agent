import pandas as pd

from app_utils import azure_sql


def _fake_conn():
    class FakeCursor:
        def execute(self, query, params=None):  # pragma: no cover - executed via call
            return self

        def fetchall(self):  # pragma: no cover - executed via call
            return []

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    return FakeConn()


def test_derive_adhoc_headers(monkeypatch):
    monkeypatch.setattr(azure_sql, "_connect", _fake_conn)
    df = pd.DataFrame({"Lane ID": ["L1"], "Foo": ["x"], "Bar": ["y"]})
    mapping = azure_sql.derive_adhoc_headers(df)
    assert mapping == {"ADHOC_INFO1": "Foo", "ADHOC_INFO2": "Bar"}

