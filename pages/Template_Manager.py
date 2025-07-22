import os
from datetime import datetime
import json
import streamlit as st

from pydantic import ValidationError

# NEW – import the schema
from schemas.template_v2 import Template
from app_utils.ui_utils import render_progress, compute_current_step

st.title("Template Manager")
st.session_state["current_step"] = compute_current_step()
progress_container = st.sidebar.empty()
render_progress(progress_container)

def validate_template_json(raw: dict) -> tuple[bool, str]:
    """
    Validate a template against the Template V2 schema.
    Returns (ok, error_message).
    """
    try:
        Template.model_validate(raw)
        return True, ""
    except ValidationError as err:  # noqa: F821
        return False, err.errors()[0]["msg"]

with st.sidebar:
    st.markdown("---")
    if st.button("Reset"):
        for k in [
            "header_suggestions",
            "header_confirmed",
            "account_suggestions",
            "account_confirmed",
        ]:
            st.session_state.pop(k, None)
        st.session_state["uploaded_file"] = None
        st.session_state["client_id"] = ""
        st.rerun()

    st.markdown("---")
    st.subheader("Template Manager")

    uploaded_template = st.file_uploader(
        "Upload Template JSON", type=["json"], key="template_upload"
    )
    if uploaded_template is not None:
        try:
            raw = json.load(uploaded_template)
            ok, msg = validate_template_json(raw)
            if ok:
                safe_name = "".join(
                    c if c.isalnum() or c in "-_" else "_" for c in raw["template_name"]
                )
                os.makedirs("templates", exist_ok=True)
                with open(os.path.join("templates", f"{safe_name}.json"), "w") as f:
                    json.dump(raw, f, indent=2)
                st.success(f"Saved template '{safe_name}'")
                st.rerun()
            else:
                st.error(f"Invalid template: {msg}")
        except Exception as e:
            st.error(f"Failed to read JSON: {e}")

    with st.expander("Existing Templates", expanded=False):
        os.makedirs("templates", exist_ok=True)
        tmpl_files = [f for f in os.listdir("templates") if f.endswith(".json")]
        for tf in tmpl_files:
            c1, c2, c3 = st.columns([2, 1, 1])
            tmpl_name = tf[:-5]
            c1.write(tmpl_name)
            with open(os.path.join("templates", tf)) as f:
                c2.download_button(
                    "Download",
                    data=f.read(),
                    file_name=tf,
                    mime="application/json",
                    key=f"dl_{tf}",
                )
            if c3.button("Delete", key=f"del_{tf}"):
                os.remove(os.path.join("templates", tf))
                st.rerun()
