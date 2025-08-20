import streamlit as st

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "app", Path(__file__).resolve().parents[1] / "🏠_Home.py"
)
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


def test_non_admin_page_removed(monkeypatch):
    pages = {
        "🏠_Home.py": {},
        "pages/📝_Template_Manager.py": {},
    }
    monkeypatch.setattr(st, "experimental_get_pages", lambda: pages, raising=False)
    st.session_state.clear()
    st.session_state["is_admin"] = False
    app.remove_template_manager_page()
    assert "pages/📝_Template_Manager.py" not in pages
