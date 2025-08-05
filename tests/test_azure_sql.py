import types

import types

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
    monkeypatch.setenv("AZURE_SQL_CONN_STRING", "Driver={};")

    codes = azure_sql.fetch_operation_codes("user@example.com")
    assert codes == ["ADSJ_VAN", "DEK1_REF"]


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
    monkeypatch.setenv("AZURE_SQL_CONN_STRING", "Driver={};")

    customers = azure_sql.fetch_customers("ADSJ")
    assert [c["BILLTO_NAME"] for c in customers] == ["Alpha", "Beta"]
