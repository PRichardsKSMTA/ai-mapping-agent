import importlib
import sys

import pytest
import streamlit as st


def test_default_dev_user_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISABLE_AUTH", "1")
    monkeypatch.delenv("DEV_USER_EMAIL", raising=False)
    st.session_state.clear()
    if "auth" in sys.modules:
        del sys.modules["auth"]
    auth = importlib.import_module("auth")
    try:
        assert auth.get_user_email() == "pete.richards@ksmta.com"
    finally:
        st.session_state.clear()
        del sys.modules["auth"]

