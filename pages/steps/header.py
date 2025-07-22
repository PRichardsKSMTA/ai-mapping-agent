"""
Header-mapping step
-------------------
• Renders a select-box table where the user maps each template column
  (`layer.fields`) to one column in the uploaded client file.
• Sets st.session_state["layer_confirmed_<idx>"] = True when the
  user clicks **Confirm**.

Assumptions
-----------
• st.session_state["uploaded_file"] already contains the file object.
• excel_utils.detect_header_row returns (records_df, columns) where
  `columns` is the list of column names detected in the client file.
• mapping_utils.suggest_header_mapping returns a dict
  {template_key: suggested_source_column or ""}.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from app_utils.excel_utils import read_tabular_file
from app_utils.mapping_utils import suggest_header_mapping


def render(layer, idx: int) -> None:
    st.header("Step — Map Headers")

    # ------------------------------------------------------------------- #
    # 1. Load the client file & extract column names                       #
    # ------------------------------------------------------------------- #
    uploaded_file = st.session_state["uploaded_file"]
    df, source_columns = read_tabular_file(uploaded_file)

    st.write("Preview of uploaded data (first 5 rows):")
    st.dataframe(df.head(), use_container_width=True)

    # ------------------------------------------------------------------- #
    # 2. Build / restore mapping state                                     #
    # ------------------------------------------------------------------- #
    mapping_key = f"header_mapping_{idx}"
    if mapping_key not in st.session_state:
        # first time: auto-suggest
        st.session_state[mapping_key] = suggest_header_mapping(
            template_fields=[f.key for f in layer.fields],  # type: ignore
            source_columns=source_columns,
        )

    mapping = st.session_state[mapping_key]

    # ------------------------------------------------------------------- #
    # 3. Render editable mapping table                                     #
    # ------------------------------------------------------------------- #
    st.subheader("Map template fields to your columns")

    cols = st.columns(3)
    cols[0].markdown("**Template Column**")
    cols[1].markdown("**Your File Column**")
    cols[2].markdown("")

    for field in layer.fields:  # type: ignore
        template_key = field.key
        required = field.required

        cols = st.columns(3)
        cols[0].write(f"{template_key}{' *' if required else ''}")

        current_val = mapping.get(template_key, "")
        new_val = cols[1].selectbox(
            label=f"map_{template_key}",
            options=[""] + source_columns,
            index=([""] + source_columns).index(current_val)
            if current_val in source_columns
            else 0,
            key=f"sb_{template_key}",
        )
        mapping[template_key] = new_val

        # Validation tick / cross
        if new_val or not required:
            cols[2].write("✅")
        else:
            cols[2].write("❌")

    st.session_state[mapping_key] = mapping  # persist edits

    # ------------------------------------------------------------------- #
    # 4. Confirm button                                                    #
    # ------------------------------------------------------------------- #
    all_required_mapped = all(
        (mapping.get(f.key) for f in layer.fields if f.required)  # type: ignore
    )

    if st.button(
        "Confirm Header Mapping",
        disabled=not all_required_mapped,
        key=f"confirm_{idx}",
    ):
        st.session_state[f"layer_confirmed_{idx}"] = True
        st.success("Header mapping saved!")
        st.rerun()
