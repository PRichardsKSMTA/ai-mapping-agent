import importlib
import sys
from typing import List

import pytest
import streamlit as st


def test_user_badge_display(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISABLE_AUTH", "1")
    st.session_state.clear()
    st.session_state["user_name"] = "Alice"

    calls: List[str] = []

    def fake_markdown(body: str, *args, **kwargs) -> None:
        calls.append(body)

    monkeypatch.setattr(st, "markdown", fake_markdown)
    monkeypatch.setattr(st, "error", lambda *a, **k: None)

    for mod in ["auth", "app"]:
        if mod in sys.modules:
            del sys.modules[mod]
    app = importlib.import_module("app")
    monkeypatch.setattr(app, "fetch_operation_codes", lambda: [])

    app.main()

    assert any("user-badge" in html and "Alice" in html for html in calls)
