import importlib
import json
import sys
from datetime import datetime

import pytest
import streamlit as st

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


@pytest.mark.parametrize("payload", [{"a": 1}, '{"a": 1}'])
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


@pytest.mark.parametrize("recover_email", [True, False])
def test_ensure_user_email_relogin(
    monkeypatch: pytest.MonkeyPatch, recover_email: bool
) -> None:
    monkeypatch.setenv("DISABLE_AUTH", "0")
    monkeypatch.setenv("AAD_CLIENT_ID", "cid")
    monkeypatch.setenv("AAD_TENANT_ID", "tid")
    monkeypatch.setenv("AAD_REDIRECT_URI", "uri")
    st.session_state.clear()
    if "auth" in sys.modules:
        del sys.modules["auth"]
    auth = importlib.import_module("auth")

    called = {"flag": False}

    def fake_ensure() -> None:
        called["flag"] = True
        if recover_email:
            st.session_state["user_email"] = "user@example.com"

    monkeypatch.setattr(auth, "_ensure_user", fake_ensure)

    captured: dict[str, str] = {}

    def fake_log(
        process_guid: str,
        operation_cd: str | None,
        template_name: str,
        friendly_name: str,
        created_by: str,
        file_name_string: str,
        process_json: dict | str,
        template_guid: str,
        adhoc_headers: dict | None = None,
    ) -> None:
        captured["created_by"] = created_by

    monkeypatch.setattr(azure_sql, "log_mapping_process", fake_log)

    email = auth.ensure_user_email()
    assert called["flag"] is True
    created_by = email or "unknown"
    azure_sql.log_mapping_process(
        "proc",
        "OP",
        "tmpl",
        "friendly",
        created_by,
        "file.csv",
        {},
        "tmpl-guid",
    )
    assert captured["created_by"] == (
        "user@example.com" if recover_email else "unknown"
    )
    st.session_state.clear()
    del sys.modules["auth"]
