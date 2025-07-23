from __future__ import annotations
import streamlit as st
import pandas as pd

from app_utils.excel_utils import read_tabular_file
from app_utils.mapping.computed_layer import resolve_computed_layer


def render(layer, idx: int):
    st.header("Step — Confirm Computed Field Logic")

    df, _ = read_tabular_file(st.session_state["uploaded_file"])

    result = resolve_computed_layer(layer.model_dump(), df)

    if result["resolved"]:
        if result["method"] == "direct":
            st.success(
                f"✅ Column **{result['source_cols'][0]}** will be copied "
                f"into **{layer.target_field}**."
            )
        else:
            st.success(
                f"✅ Expression will create **{layer.target_field}**:\n\n"
                f"```python\n{result['expression']}\n```"
            )
    else:
        st.error(
            "⚠️ No candidate rule matched your data. "
            f"You'll need to create **{layer.target_field}** manually."
        )

    if st.button("Confirm Computed Layer", key=f"confirm_{idx}"):
        st.session_state[f"computed_result_{idx}"] = result
        st.session_state[f"layer_confirmed_{idx}"] = True
        st.rerun()
