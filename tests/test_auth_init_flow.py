import importlib
import sys

import pytest
import streamlit as st


def test_initiate_flow_recovers_missing_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AAD_CLIENT_ID", "cid")
    monkeypatch.setenv("AAD_CLIENT_SECRET", "sec")
    monkeypatch.setenv("AAD_TENANT_ID", "tid")
    monkeypatch.setenv("AAD_REDIRECT_URI", "http://localhost")
    monkeypatch.delenv("DISABLE_AUTH", raising=False)
    st.session_state.clear()

    if "auth" in sys.modules:
        del sys.modules["auth"]
    auth = importlib.import_module("auth")

    class DummyApp:
        def initiate_auth_code_flow(self, **kwargs):
            return {"state": "s1", "auth_uri": "http://login"}

    monkeypatch.setattr(auth, "_build_msal_app", lambda: DummyApp())

    st.session_state["msal_state"] = "missing"
    auth._FLOW_CACHE.clear()

    url = auth._initiate_flow()

    assert url == "http://login"
    assert st.session_state["msal_state"] == "s1"
    assert auth._FLOW_CACHE["s1"]["auth_uri"] == "http://login"

    st.session_state.clear()
    del sys.modules["auth"]
