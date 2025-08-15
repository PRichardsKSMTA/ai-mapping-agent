import importlib
import sys

import pytest
import streamlit as st
import msal


def test_build_msal_app_uses_confidential(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AAD_CLIENT_ID", "cid")
    monkeypatch.setenv("AAD_CLIENT_SECRET", "secret")
    monkeypatch.setenv("AAD_TENANT_ID", "tid")
    monkeypatch.setenv("AAD_REDIRECT_URI", "http://localhost")
    monkeypatch.delenv("DISABLE_AUTH", raising=False)
    st.session_state.clear()
    if "auth" in sys.modules:
        del sys.modules["auth"]

    captured: dict[str, str] = {}

    class DummyConfidential:
        def __init__(self, client_id: str, authority: str, client_credential: str) -> None:
            captured["client_id"] = client_id
            captured["authority"] = authority
            captured["client_credential"] = client_credential

    monkeypatch.setattr(msal, "ConfidentialClientApplication", DummyConfidential)
    auth = importlib.import_module("auth")

    app = auth._build_msal_app()
    assert isinstance(app, DummyConfidential)
    assert captured == {
        "client_id": "cid",
        "authority": "https://login.microsoftonline.com/tid",
        "client_credential": "secret",
    }

    st.session_state.clear()
    del sys.modules["auth"]
