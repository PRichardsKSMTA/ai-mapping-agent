from __future__ import annotations
"""
Formula Dialog – stable buttons and no NameError
------------------------------------------------
Buttons live inside the dialog; clicks are detected because their keys
are stable.  “Clear” refreshes in-place, “Save” persists & closes.
"""

import math
import re
import uuid
from typing import List

import pandas as pd
import streamlit as st

from app_utils.suggestion_store import add_suggestion

# ─────────────────────────── configuration ────────────────────────────
OPS_DISPLAY_MAP = {r"\+": "+", r"\-": "-", r"\*": "*", "/": "/", "(": "(", ")": ")"}
OPS: List[str] = list(OPS_DISPLAY_MAP.keys())

RETURN_KEY_TEMPLATE = "formula_expr_{key}"
ROW_CAPACITY = 5  # pill grid width units


# ─────────────────────────── helpers ──────────────────────────────────
def _token_units(tok: str) -> int:
    actual = OPS_DISPLAY_MAP.get(tok, tok)
    if actual in {"+", "-", "*", "/"}:
        return 1
    return min(3, max(1, math.ceil(len(actual) / 12)))


# ─────────────────────────── main entrypoint ──────────────────────────
def open_formula_dialog(df: pd.DataFrame, dialog_key: str) -> None:
    """Open the modal formula builder (gear-icon handler)."""
    result_key = RETURN_KEY_TEMPLATE.format(key=dialog_key)
    expr_key = f"{dialog_key}_expr_text"

    # Prefill on first open each run
    if result_key in st.session_state and expr_key not in st.session_state:
        st.session_state[expr_key] = st.session_state[result_key]

    # ═════════════════════════ inner helpers ══════════════════════════
    def _append_token(token: str) -> None:
        actual = OPS_DISPLAY_MAP.get(token, token)
        frag = f" df['{token}'] " if token not in OPS else f" {actual} "
        st.session_state[expr_key] += frag

    def _render_row(tokens: List[str]) -> None:
        if not tokens:
            return
        cols = st.columns([_token_units(t) for t in tokens])
        for i, tok in enumerate(tokens):
            cols[i].button(
                tok,
                key=f"{dialog_key}_{tok}_{i}",
                on_click=_append_token,
                args=(tok,),
            )

    def _valid(e: str) -> bool:
        return (
            e
            and e.rstrip()[-1] not in {"+", "-", "*", "/", "("}
            and not e.endswith("df[")
        )
        
    def reset_expr():
        st.session_state[expr_key] = ""

    def _preview(e: str) -> bool:
        if not _valid(e):
            st.info("Build your expression or click tokens above.")
            return bool(e)
        try:
            res = eval(e, {"df": df})                   # noqa: S307 – user code
            if not isinstance(res, pd.Series):
                res = pd.Series([res] * len(df))
            st.dataframe(
                pd.DataFrame({"Result": res}).head(),
                use_container_width=True,
            )
            return True
        except Exception as exc:                        # noqa: BLE001
            st.error(f"❌ {exc}")
            return False

    # ════════════════════════ dialog definition ═══════════════════════
    @st.dialog(f"Build Formula for '{dialog_key}'", width="large")
    def _dialog() -> None:
        st.session_state.setdefault(expr_key, "")

        # CSS to keep pills tidy
        st.markdown(
            "<style>.stButton>button{white-space:nowrap;margin:0 0.25rem 0.25rem 0}</style>",
            unsafe_allow_html=True,
        )
        st.markdown("#### Click a token or type directly:")

        # ── token pills grid ──
        row, units = [], 0
        for token in list(df.columns) + OPS:
            u = _token_units(token)
            if units + u > ROW_CAPACITY:
                _render_row(row)
                row, units = [], 0
            row.append(token)
            units += u
        _render_row(row)

        # ── editor ──
        st.text_area("Formula", key=expr_key, height=150)

        # ── preview & buttons ──
        expr = st.session_state[expr_key].strip()
        save_ready = _preview(expr)

        col_clear, col_save = st.columns(2)

        col_clear.button("⟲ Clear", key=f"{dialog_key}_clear", on_click=reset_expr)
            # st.rerun()

        if col_save.button("💾 Save", key=f"{dialog_key}_save", disabled=not save_ready):
            st.session_state[result_key] = expr
            st.session_state[f"{result_key}_display"] = re.sub(r"df\['([^']+)'\]", r"\1", expr)

            add_suggestion(
                {
                    "template": st.session_state["current_template"],
                    "field": dialog_key,
                    "type": "formula",
                    "formula": expr,
                    "columns": re.findall(r"df\['([^']+)'\]", expr),
                    "display": st.session_state[f"{result_key}_display"],
                }
            )
            st.session_state.pop(expr_key, None)
            st.rerun()  # closes modal

    _dialog()  # ← actually displays the modal
