"""Streamlit dialog for managing mapping suggestions."""

from __future__ import annotations

import json
import os
from typing import List

import streamlit as st

try:  # pragma: no cover - dependency optional in tests
    from streamlit_tags import st_tags
except Exception:  # noqa: BLE001
    def st_tags(*, label: str, text: str, value: list[str], key: str):
        del label, text, key
        return value

from app_utils.suggestion_store import add_suggestion, delete_suggestion, get_suggestions


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
            direct = [s for s in suggestions if s.get("type") != "formula"]
            formulas = [s for s in suggestions if s.get("type") == "formula"]

            def _label(s: dict) -> str:
                if s.get("type") == "formula":
                    return s.get("display") or s.get("formula", "")
                return s.get("display") or ",".join(s.get("columns", []))

            direct_labels = [_label(s) for s in direct]
            new_direct = st_tags(
                label="Columns",
                text="Add column and press enter",
                value=direct_labels,
                key=f"tags_{field}",
            )
            removed = set(direct_labels) - set(new_direct)
            for lbl in removed:
                match = next((d for d in direct if _label(d) == lbl), None)
                if match:
                    delete_suggestion(
                        template_name,
                        field,
                        columns=match.get("columns"),
                    )
                    st.session_state.pop(f"tags_{field}", None)
                    st.session_state["suggestions_dialog_open"] = (
                        filename,
                        template_name,
                    )
                    st.rerun()
            added = set(new_direct) - set(direct_labels)
            for lbl in added:
                cols = [c.strip() for c in lbl.split(",") if c.strip()]
                add_suggestion(
                    {
                        "template": template_name,
                        "field": field,
                        "type": "direct",
                        "columns": cols,
                        "display": lbl,
                    }
                )
                st.session_state.pop(f"tags_{field}", None)
                st.session_state["suggestions_dialog_open"] = (
                    filename,
                    template_name,
                )
                st.rerun()

            formula_labels = [_label(s) for s in formulas]
            new_formulas = st_tags(
                label="Formulas",
                text="Add formula and press enter",
                value=formula_labels,
                key=f"form_{field}",
            )
            removed_f = set(formula_labels) - set(new_formulas)
            for lbl in removed_f:
                match = next((f for f in formulas if _label(f) == lbl), None)
                if match:
                    delete_suggestion(
                        template_name,
                        field,
                        formula=match.get("formula"),
                    )
                    st.session_state.pop(f"form_{field}", None)
                    st.session_state["suggestions_dialog_open"] = (
                        filename,
                        template_name,
                    )
                    st.rerun()
            added_f = set(new_formulas) - set(formula_labels)
            for lbl in added_f:
                add_suggestion(
                    {
                        "template": template_name,
                        "field": field,
                        "type": "formula",
                        "formula": lbl,
                        "columns": [],
                        "display": "",
                    }
                )
                st.session_state.pop(f"form_{field}", None)
                st.session_state["suggestions_dialog_open"] = (
                    filename,
                    template_name,
                )
                st.rerun()

    _dlg()

