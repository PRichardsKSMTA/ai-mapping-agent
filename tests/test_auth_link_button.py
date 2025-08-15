import importlib
import sys

import pytest
import streamlit as st


def _import_auth(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AAD_CLIENT_ID", "cid")
    monkeypatch.setenv("AAD_CLIENT_SECRET", "sec")
    monkeypatch.setenv("AAD_TENANT_ID", "tid")
    monkeypatch.setenv("AAD_REDIRECT_URI", "http://localhost")
    monkeypatch.delenv("DISABLE_AUTH", raising=False)
    st.session_state.clear()
    sys.modules.pop("auth", None)
    return importlib.import_module("auth")


def test_ensure_user_renders_link_button(monkeypatch: pytest.MonkeyPatch) -> None:
    auth = _import_auth(monkeypatch)

    monkeypatch.setattr(auth, "_complete_flow", lambda: None)
    monkeypatch.setattr(auth, "_initiate_flow", lambda: "http://login")

    called: dict[str, str] = {}

    def fake_link_button(label: str, url: str) -> None:
        called["label"] = label
        called["url"] = url

    monkeypatch.setattr(st, "link_button", fake_link_button)

    def stop() -> None:
        raise RuntimeError("stopped")

    monkeypatch.setattr(st, "stop", stop)

    with pytest.raises(RuntimeError):
        auth._ensure_user()

    assert called == {"label": "Sign in with Microsoft", "url": "http://login"}
