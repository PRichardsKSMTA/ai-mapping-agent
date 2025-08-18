"""Streamlit dialog for managing mapping suggestions."""

from __future__ import annotations

import json
import os
from typing import List

import streamlit as st

from app_utils.suggestion_store import (
    add_suggestion,
    delete_suggestion,
    get_suggestions,
    update_suggestion,
)


def _field_names(tpl: dict) -> List[str]:
    names: List[str] = []
    for layer in tpl.get("layers", []):
        for field in layer.get("fields", []):
            target = field.get("key") or field.get("target")
            if target:
                names.append(target)
    return names


def edit_suggestions(filename: str, template_name: str) -> None:
    """Render dialog to manage suggestions for ``template_name``."""

    path = os.path.join("templates", filename)
    try:
        tpl = json.load(open(path))
    except Exception as err:  # noqa: BLE001
        st.error(f"Failed to load template: {err}")
        return

    @st.dialog(f"Manage Suggestions – {template_name}", width="large")
    def _dlg() -> None:
        for field in _field_names(tpl):
            st.subheader(field)
            suggestions = get_suggestions(template_name, field)
            for idx, s in enumerate(suggestions):
                cols_val = ",".join(s.get("columns", []))
                cols_key = f"sg_cols_{field}_{idx}"
                disp_key = f"sg_disp_{field}_{idx}"
                if s.get("type") == "formula":
                    st.text_input("Formula", s.get("formula", ""), key=cols_key, disabled=True)
                else:
                    st.text_input("Columns", cols_val, key=cols_key)
                st.text_input("Display", s.get("display", ""), key=disp_key)
                c1, c2 = st.columns(2)
                if c1.button("Update", key=f"upd_{field}_{idx}"):
                    new_cols = None
                    if s.get("type") != "formula":
                        raw = st.session_state.get(cols_key, "")
                        new_cols = [c.strip() for c in raw.split(",") if c.strip()]
                    update_suggestion(
                        template_name,
                        field,
                        columns=s.get("columns"),
                        formula=s.get("formula"),
                        display=st.session_state.get(disp_key, ""),
                        new_columns=new_cols,
                    )
                    st.rerun()
                if c2.button("Delete", key=f"del_{field}_{idx}"):
                    delete_suggestion(
                        template_name,
                        field,
                        columns=s.get("columns"),
                        formula=s.get("formula"),
                    )
                    st.rerun()

            cols_new = f"new_cols_{field}"
            form_new = f"new_formula_{field}"
            disp_new = f"new_disp_{field}"
            st.text_input("Columns", key=cols_new)
            st.text_input("Formula", key=form_new)
            st.text_input("Display", key=disp_new)
            if st.button(f"Add {field}", key=f"add_{field}"):
                cols = [
                    c.strip()
                    for c in st.session_state.get(cols_new, "").split(",")
                    if c.strip()
                ]
                formula = st.session_state.get(form_new) or None
                suggestion = {
                    "template": template_name,
                    "field": field,
                    "type": "formula" if formula else "direct",
                    "formula": formula,
                    "columns": cols,
                    "display": st.session_state.get(disp_new, ""),
                }
                add_suggestion(suggestion)
                st.rerun()

    _dlg()

