from __future__ import annotations
"""
Header-mapping step – now shows friendly formula text.
"""

import streamlit as st
import pandas as pd

from app_utils.excel_utils import read_tabular_file
from app_utils.mapping_utils import suggest_header_mapping
from app_utils.ui.formula_dialog import (
    open_formula_dialog,
    RETURN_KEY_TEMPLATE,
)

# ------------------------------------------------------------------ #
# Tiny CSS tweaks                                                    #
# ------------------------------------------------------------------ #
st.markdown(
    """
    <style>
    .stSelectbox select {max-width: 150px;}
    .stButton>button    {padding: 0.15rem 0.5rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def render(layer, idx: int) -> None:
    st.header("Step 1 – Map Source Columns to Template Fields")

    # ------------------------------------------------------------------ #
    # 1. Load client data                                               #
    # ------------------------------------------------------------------ #
    df, source_cols = read_tabular_file(st.session_state["uploaded_file"])

    # ------------------------------------------------------------------ #
    # 2. Initialise / restore mapping dict                              #
    # ------------------------------------------------------------------ #
    map_key = f"header_mapping_{idx}"
    if map_key not in st.session_state:
        auto = suggest_header_mapping([f.key for f in layer.fields], source_cols)  # type: ignore
        st.session_state[map_key] = {k: {"src": v} if v else {} for k, v in auto.items()}

    mapping = st.session_state[map_key]

    st.caption("• ✅ mapped • ❌ required & missing")

    # ------------------------------------------------------------------ #
    # 3. Render rows                                                    #
    # ------------------------------------------------------------------ #
    for field in layer.fields:  # type: ignore
        key = field.key
        required = field.required

        row = st.columns([3, 1, 4, 3, 1])   # Source | Gear | Expr | Template | Status

        # ---------------- Source dropdown -----------------------------
        src_val = mapping.get(key, {}).get("src", "")
        new_src = row[0].selectbox(
            f"src_{key}",
            options=[""] + source_cols,
            index=([""] + source_cols).index(src_val) if src_val in source_cols else 0,
            key=f"src_{key}",
            label_visibility="collapsed",
        )
        if new_src:
            mapping[key] = {"src": new_src}
        elif "src" in mapping.get(key, {}):
            mapping[key] = {}

        # ---------------- Gear button (Formula Dialog) ----------------
        if row[1].button("⚙️", key=f"calc_{key}", help="Formula builder"):
            open_formula_dialog(df, key)

        # Handle dialog save (pythonic + display)
        res_key = RETURN_KEY_TEMPLATE.format(key=key)
        res_disp_key = f"{res_key}_display"

        if res_key in st.session_state:
            mapping[key] = {
                "expr": st.session_state.pop(res_key),
                "expr_display": st.session_state.pop(res_disp_key, ""),
            }

        # ---------------- Expression display --------------------------
        expr_display = mapping.get(key, {}).get("expr_display") or mapping.get(key, {}).get("expr", "")
        row[2].markdown(f"`{expr_display}`" if expr_display else "")

        # ---------------- Template field label ------------------------
        row[3].markdown(f"**{key}**")

        # ---------------- Status icon ---------------------------------
        status = (
            "✅" if mapping.get(key, {}).get("src") else
            "⚙️" if "expr" in mapping.get(key, {}) else
            ("❌" if required else "—")
        )
        row[4].markdown(status)

    st.session_state[map_key] = mapping   # persist row edits

    # ------------------------------------------------------------------ #
    # 4. Confirm button                                                 #
    # ------------------------------------------------------------------ #
    ready = all(
        (("src" in m and m["src"]) or ("expr" in m)) if f.required else True
        for f, m in zip(layer.fields, mapping.values())  # type: ignore
    )

    if st.button("Confirm Header Mapping", disabled=not ready, key=f"confirm_{idx}"):
        st.session_state[f"layer_confirmed_{idx}"] = True
        st.session_state["auto_computed_confirm"] = True   # skip computed layer
        st.rerun()
