import importlib
import sys

import pytest
import streamlit as st
from streamlit.runtime.state.query_params import QueryParams


def test_complete_flow_accepts_query_params(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AAD_CLIENT_ID", "cid")
    monkeypatch.setenv("AAD_TENANT_ID", "tid")
    monkeypatch.setenv("AAD_REDIRECT_URI", "http://localhost")
    monkeypatch.delenv("DISABLE_AUTH", raising=False)
    st.session_state.clear()

    if "auth" in sys.modules:
        del sys.modules["auth"]
    auth = importlib.import_module("auth")

    class DummyApp:
        def __init__(self) -> None:
            self.called_with: dict | None = None

        def acquire_token_by_auth_code_flow(self, flow, data):
            assert isinstance(data, dict)
            self.called_with = data
            return {
                "id_token": "tok",
                "id_token_claims": {"preferred_username": "user@example.com", "groups": []},
            }

    dummy_app = DummyApp()
    monkeypatch.setattr(auth, "_build_msal_app", lambda: dummy_app)

    state = "abc"
    auth._FLOW_CACHE[state] = {"state": state}
    st.query_params = QueryParams({"code": ["c123"], "state": [state]})

    auth._complete_flow()

    assert dummy_app.called_with == {"code": "c123", "state": state}
    assert st.session_state.get("id_token") == "tok"

    st.session_state.clear()
    del sys.modules["auth"]
