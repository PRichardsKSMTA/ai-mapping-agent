import importlib
import sys

import pytest
import streamlit as st


def test_default_dev_user_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISABLE_AUTH", "1")
    monkeypatch.delenv("DEV_USER_NAME", raising=False)
    monkeypatch.delenv("DEV_USER_EMAIL", raising=False)
    st.session_state.clear()
    for mod in ["auth"]:
        if mod in sys.modules:
            del sys.modules[mod]
    auth = importlib.import_module("auth")
    try:
        assert auth.get_user_name() == "pete.richards"
    finally:
        st.session_state.clear()
        del sys.modules["auth"]
