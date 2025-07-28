"""
Lookup mapping UI – maps client values → dictionary values.
"""

from __future__ import annotations
import streamlit as st
import pandas as pd

from app_utils.mapping_utils import match_lookup_values
from app_utils.mapping.lookup_layer import gpt_lookup_completion
from app_utils.excel_utils import read_tabular_file
from schemas.template_v2 import Template


def render(layer, idx: int):
    st.header("Step — Map Look-up Values")

    # ------------------------------------------------------------------ #
    # 0. Get template object from session (safety check)                 #
    # ------------------------------------------------------------------ #
    template_raw = st.session_state.get("template")
    if template_raw is None:
        st.error("🛑 Template not found in session. Please select a template.")
        return

    template = Template.model_validate(template_raw)

    # ------------------------------------------------------------------ #
    # 1. Load source column values                                       #
    # ------------------------------------------------------------------ #
    sheet_name = getattr(layer, "sheet", None) or st.session_state.get(
        "upload_sheet", 0
    )
    with st.spinner("Loading file..."):
        df, _ = read_tabular_file(
            st.session_state["uploaded_file"], sheet_name=sheet_name
        )
    src_col = layer.source_field
    if src_col not in df.columns:
        st.error(f"Column **{src_col}** not found in uploaded file.")
        return

    unique_vals = sorted(df[src_col].dropna().unique().astype(str))

    # ------------------------------------------------------------------ #
    # 2. Load dictionary values from template                            #
    # ------------------------------------------------------------------ #
    try:
        records = getattr(template, layer.dictionary_sheet)
        dict_values = [rec[layer.target_field] for rec in records]
    except Exception:
        st.error("Dictionary sheet not yet supported for this template.")
        return

    # ------------------------------------------------------------------ #
    # 3. Build or restore mapping                                        #
    # ------------------------------------------------------------------ #
    key_map = f"lookup_mapping_{idx}"
    if key_map not in st.session_state:
        st.session_state[key_map] = match_lookup_values(unique_vals, dict_values)

    mapping = st.session_state[key_map]
    ai_flag = f"lookup_ai_done_{idx}"
    if not st.session_state.get(ai_flag):
        unmapped_init = [k for k, v in mapping.items() if v == ""]
        if unmapped_init:
            try:
                with st.spinner("Querying GPT..."):
                    suggestions = gpt_lookup_completion(unmapped_init, dict_values)
                for src, match in suggestions.items():
                    if match:
                        mapping[src] = match
                st.session_state[key_map] = mapping
            except Exception as e:  # noqa: BLE001
                st.error(str(e))
            finally:
                st.session_state[ai_flag] = True
                st.rerun()
        else:
            st.session_state[ai_flag] = True

    edited = st.data_editor(
        pd.DataFrame(
            {"Source": list(mapping.keys()), "Match": list(mapping.values())}
        ),
        num_rows="dynamic",
        key=f"editor_{idx}",
    )
    mapping = dict(zip(edited["Source"], edited["Match"]))
    st.session_state[key_map] = mapping

    # ------------------------------------------------------------------ #
    # 4. Validation & confirm                                            #
    # ------------------------------------------------------------------ #
    unmapped = [k for k, v in mapping.items() if v == ""]
    if unmapped:
        st.warning(f"{len(unmapped)} values still unmapped.")
    else:
        st.success("All values mapped!")

    if st.button(
        "Confirm Look-up Mapping",
        disabled=bool(unmapped),
        key=f"confirm_{idx}",
    ):
        st.session_state[f"layer_confirmed_{idx}"] = True
        st.rerun()
