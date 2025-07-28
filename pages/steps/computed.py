from __future__ import annotations
import streamlit as st
import pandas as pd

from app_utils.excel_utils import read_tabular_file
from app_utils.ui.expression_builder import build_expression
from schemas.template_v2 import Template


def render(layer, idx: int):
    st.header("Step — Configure Computed Field")

    df, _ = read_tabular_file(
        st.session_state["uploaded_file"],
        sheet_name=st.session_state.get("upload_sheet", 0),
    )

    # 1. Decide Direct vs Computed
    mode_key = f"computed_mode_{idx}"
    mode = st.radio(
        "How should this field be populated?",
        options=["Direct (one column)", "Computed (expression)"],
        key=mode_key,
    )

    result_key = f"computed_result_{idx}"
    result = st.session_state.get(result_key, {"resolved": False})

    # 2A. Direct mapping UI
    if mode.startswith("Direct"):
        col = st.selectbox(
            "Select source column",
            options=[""] + list(df.columns),
            index=([""] + list(df.columns)).index(result.get("source_cols", [""])[0])
            if result.get("source_cols")
            else 0,
        )

        if col:
            st.success(f"`{col}` → **{layer.target_field}**")
            result.update(
                {
                    "resolved": True,
                    "method": "direct",
                    "source_cols": [col],
                    "expression": None,
                }
            )
        else:
            st.info("Choose a column to continue.")
            result["resolved"] = False

    # 2B. Computed expression UI
    else:
        expr, valid = build_expression(df, key_prefix=f"expr_{idx}")
        if valid:
            st.success(f"✅ Expression valid:\n\n`{expr}`")
            result.update(
                {
                    "resolved": True,
                    "method": "derived",
                    "source_cols": [],  # can be filled by parser later
                    "expression": expr,
                }
            )
        else:
            result["resolved"] = False

    # 3. Confirm button
    st.session_state[result_key] = result
    if st.button(
        "Confirm Computed Field",
        disabled=not result.get("resolved"),
        key=f"confirm_{idx}",
    ):
        st.session_state[f"layer_confirmed_{idx}"] = True
        st.rerun()
