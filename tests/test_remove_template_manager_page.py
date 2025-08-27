import streamlit as st

import Home


def test_non_admin_page_removed(monkeypatch):
    pages = {
        "Home.py": {},
        "pages/Template_Manager.py": {},
    }
    monkeypatch.setattr(st, "experimental_get_pages", lambda: pages, raising=False)
    st.session_state.clear()
    st.session_state["is_admin"] = False
    Home.remove_template_manager_page()
    assert "pages/Template_Manager.py" not in pages
