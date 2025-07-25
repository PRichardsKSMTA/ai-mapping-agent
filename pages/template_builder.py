import json
import os
import streamlit as st
from pydantic import ValidationError

from auth import require_employee
from schemas.template_v2 import Template
from app_utils.excel_utils import read_tabular_file
from app_utils.template_builder import build_header_template
from app_utils.ui_utils import render_progress, compute_current_step


@require_employee
def show():
    st.title("Template Builder")
    st.session_state["current_step"] = compute_current_step()
    progress_container = st.sidebar.empty()
    render_progress(progress_container)

    tmpl_name = st.text_input("Template Name", key="tb_name")
    sample = st.file_uploader(
        "Upload Sample CSV or Excel",
        type=["csv", "xls", "xlsx", "xlsm"],
        key="tb_sample",
    )

    if sample is not None:
        _, cols = read_tabular_file(sample)
        st.session_state["tb_columns"] = cols
    columns = st.session_state.get("tb_columns", [])

    required = st.session_state.get("tb_required", {})
    if columns:
        st.subheader("Mark required fields")
        for col in columns:
            required[col] = st.checkbox(
                col, key=f"req_{col}", value=required.get(col, False)
            )
        st.session_state["tb_required"] = required

    if st.button("Save Template", disabled=not (tmpl_name and columns)):
        tpl = build_header_template(tmpl_name, columns, required)
        try:
            Template.model_validate(tpl)
        except ValidationError as err:  # noqa: F841
            st.error(f"Invalid template: {err}")
        else:
            safe_name = "".join(
                c if c.isalnum() or c in "-_" else "_" for c in tmpl_name
            )
            os.makedirs("templates", exist_ok=True)
            with open(os.path.join("templates", f"{safe_name}.json"), "w") as f:
                json.dump(tpl, f, indent=2)
            st.success(f"Saved template '{safe_name}'")


show()
