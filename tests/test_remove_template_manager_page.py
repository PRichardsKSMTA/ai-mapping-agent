import streamlit as st

import app


def test_non_admin_page_removed(monkeypatch):
    pages = {
        "app.py": {},
        "pages/template_manager.py": {},
    }
    monkeypatch.setattr(st, "experimental_get_pages", lambda: pages, raising=False)
    st.session_state.clear()
    st.session_state["is_admin"] = False
    app.remove_template_manager_page()
    assert "pages/template_manager.py" not in pages
