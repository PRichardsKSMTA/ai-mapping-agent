import importlib
import sys

import pytest
import streamlit as st


def test_initiate_flow_rebuilds_after_rerun(monkeypatch: pytest.MonkeyPatch) -> None:
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
        def __init__(self) -> None:
            self.count = 0

        def initiate_auth_code_flow(self, *a, **k):  # pragma: no cover - simple stub
            self.count += 1
            return {"state": f"s{self.count}", "auth_uri": f"http://login/{self.count}"}

    dummy_app = DummyApp()
    monkeypatch.setattr(auth, "_build_msal_app", lambda: dummy_app)

    url1 = auth._initiate_flow()
    assert url1
    assert st.session_state["msal_state"] in auth._FLOW_CACHE

    auth._FLOW_CACHE.clear()

    url2 = auth._initiate_flow()
    assert url2
    assert st.session_state["msal_state"] in auth._FLOW_CACHE

    st.session_state.clear()
    del sys.modules["auth"]
