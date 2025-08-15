import importlib
import sys

import pytest
import streamlit as st


def test_import_auto_disables_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Module should load without secrets and auto-disable auth."""
    for env in [
        "AAD_CLIENT_ID",
        "AAD_CLIENT_SECRET",
        "AAD_TENANT_ID",
        "AAD_REDIRECT_URI",
        "DISABLE_AUTH",
    ]:
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr(st, "secrets", {})
    st.session_state.clear()
    sys.modules.pop("auth", None)
    auth = importlib.import_module("auth")
    try:
        assert auth.DISABLE_AUTH is True
        assert auth.require_login(lambda: 42)() == 42
    finally:
        st.session_state.clear()
        sys.modules.pop("auth", None)

