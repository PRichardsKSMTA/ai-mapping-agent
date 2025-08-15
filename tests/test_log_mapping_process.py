import pytest
from datetime import datetime
import json

from app_utils import azure_sql


def _fake_conn(captured: dict):
    class FakeCursor:
        def execute(self, query, params):  # pragma: no cover - executed via call
            captured["query"] = query
            captured["params"] = params
            return self

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    return FakeConn()


@pytest.mark.parametrize("payload", [{"a": 1}, "{\"a\": 1}"])
def test_log_mapping_process(monkeypatch, payload):
    captured: dict = {}
    monkeypatch.setattr(azure_sql, "_connect", lambda: _fake_conn(captured))
    adhoc = {"ADHOC_INFO1": "Foo"}
    azure_sql.log_mapping_process(
        "proc",
        "OP",
        "template-name",
        "Friendly",
        "user@example.com",
        "file.csv",
        payload,
        "tmpl-guid",
        adhoc,
    )
    assert "MAPPING_AGENT_PROCESSES" in captured["query"]
    assert "OPERATION_CD" in captured["query"]
    params = captured["params"]
    assert params[0] == "proc"
    assert params[1] == "OP"
    assert params[2] == "template-name"
    assert params[3] == "Friendly"
    assert params[4] == "user@example.com"
    assert isinstance(params[5], datetime)
    assert params[6] == "file.csv"
    stored = json.loads(params[7])
    expected = json.loads(payload) if isinstance(payload, str) else payload
    expected["adhoc_headers"] = adhoc
    assert stored == expected
    assert params[8] == "tmpl-guid"
