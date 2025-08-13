import importlib
import sys

import pytest
import streamlit as st


def test_get_config_prefers_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISABLE_AUTH", "1")
    st.session_state.clear()
    monkeypatch.setattr(st.secrets, "_secrets", {"FOO": "secret"}, raising=False)
    if "auth" in sys.modules:
        del sys.modules["auth"]
    auth = importlib.import_module("auth")
    try:
        monkeypatch.setenv("FOO", "env")
        assert auth._get_config("FOO") == "secret"
        monkeypatch.delenv("FOO", raising=False)
        monkeypatch.setenv("BAR", "envbar")
        assert auth._get_config("BAR") == "envbar"
        assert auth._get_config("MISSING", "default") == "default"
    finally:
        st.session_state.clear()
        del sys.modules["auth"]
