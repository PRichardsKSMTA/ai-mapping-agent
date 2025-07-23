"""
Header-mapping step — compact table (Source → Calculator → Expression → Template → Status)

• Source column dropdown auto-populated via suggest_header_mapping().
• 🖩 button opens a Formula Dialog (modal) to build or edit the expression.
• Dialog created in `app_utils/ui/formula_dialog.py`.
• Status icons:
      ✅ direct-mapped
      ❌ required & missing
"""

from __future__ import annotations
import streamlit as st
import pandas as pd

from app_utils.excel_utils import read_tabular_file
from app_utils.mapping_utils import suggest_header_mapping
from app_utils.ui.formula_dialog import (
    open_formula_dialog,
    RETURN_KEY_TEMPLATE,
)

# ------------------------------------------------------------------ #
# Small CSS tweaks for narrow widgets                                #
# ------------------------------------------------------------------ #
st.markdown(
    """
    <style>
    .stSelectbox select {max-width: 150px;}
    .stButton>button {padding: 0.15rem 0.5rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def render(layer, idx: int) -> None:
    st.header("Step 1 – Map Source Columns to Template Fields")

    # ------------------------------------------------------------------ #
    # 1  Load client data                                                #
    # ------------------------------------------------------------------ #
    df, source_cols = read_tabular_file(st.session_state["uploaded_file"])

    # ------------------------------------------------------------------ #
    # 2  Initialise / restore mapping dict                               #
    # ------------------------------------------------------------------ #
    map_key = f"header_mapping_{idx}"
    if map_key not in st.session_state:
        auto = suggest_header_mapping([f.key for f in layer.fields], source_cols)  # type: ignore
        st.session_state[map_key] = {k: {"src": v} if v else {} for k, v in auto.items()}
    mapping = st.session_state[map_key]

    st.caption('''
               • ✅ mapped  
               • ❌ required & missing
               ''')

    # ------------------------------------------------------------------ #
    # 3  Render rows                                                     #
    # ------------------------------------------------------------------ #
    for field in layer.fields:  # type: ignore
        key = field.key
        required = field.required

        # Source | Calc btn | Expr | Template | Status
        row = st.columns([3, 1, 4, 3, 1])

        # --- Source dropdown ------------------------------------------
        src_val = mapping.get(key, {}).get("src", "")
        new_src = row[0].selectbox(
            f"src_{key}",                     # non-empty label for a11y
            options=[""] + source_cols,
            index=([""] + source_cols).index(src_val) if src_val in source_cols else 0,
            key=f"src_{key}",
            label_visibility="collapsed",
        )
        if new_src:
            mapping[key] = {"src": new_src}
        elif "src" in mapping.get(key, {}):
            mapping[key] = {}

        # --- Calculator button ----------------------------------------
        if row[1].button("⚙️", key=f"calc_{key}", help="Formula builder"):
            open_formula_dialog(df, key)

        # Handle dialog save
        res_key = RETURN_KEY_TEMPLATE.format(key=key)
        if res_key in st.session_state:
            mapping[key] = {"expr": st.session_state.pop(res_key)}

        # --- Expression display --------------------------------------
        expr_display = mapping.get(key, {}).get("expr", "")
        row[2].markdown(f"`{expr_display}`" if expr_display else "")

        # --- Template field label ------------------------------------
        row[3].markdown(f"**{key}**")

        # --- Status icon ---------------------------------------------
        status = (
            "✅" if mapping.get(key, {}).get("src") else
            "⚙️" if "expr" in mapping.get(key, {}) else
            ("❌" if required else "—")
        )
        row[4].markdown(status)

    # Persist
    st.session_state[map_key] = mapping

    # ------------------------------------------------------------------ #
    # 4  Confirm button                                                  #
    # ------------------------------------------------------------------ #
    ready = all(
        (("src" in m and m["src"]) or ("expr" in m)) if f.required else True
        for f, m in zip(layer.fields, mapping.values())  # type: ignore
    )

    if st.button("Confirm Header Mapping", disabled=not ready, key=f"confirm_{idx}"):
        st.session_state[f"layer_confirmed_{idx}"] = True
        st.session_state["auto_computed_confirm"] = True  # skip computed layer later
        st.rerun()
