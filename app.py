"""
AI Mapping Agent – Streamlit entrypoint
--------------------------------------

Key features
• Loads a JSON template (v2 schema) and builds wizard steps dynamically
  from its `layers` array.
• Validates the template with Pydantic (strict: no v1 accepted).
• Lets the user upload a client Excel/CSV file.
• Walks through each layer (header → lookup → computed → …),
  setting `st.session_state["layer_confirmed_<idx>"] = True`
  when a layer is completed.
• Shows a sidebar progress tracker driven by app_utils.ui_utils.

Stub pages (`pages.lookup_step`, `pages.computed_step`) are minimal;
you will flesh them out in Phase C.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
from pydantic import ValidationError

from schemas.template_v2 import Template
from app_utils.ui_utils import (
    render_progress,
    set_steps_from_template,
)

# ---------------------------------------------------------------------------
# 0.  Page config & helpers
# ---------------------------------------------------------------------------

st.set_page_config(page_title="AI Mapping Agent", layout="wide")
st.title("AI Mapping Agent")

TEMPLATES_DIR = Path("templates")
TEMPLATES_DIR.mkdir(exist_ok=True)


def reset_layer_confirmations() -> None:
    """Clear any stored layer_confirmed_* flags."""
    for key in list(st.session_state.keys()):
        if key.startswith("layer_confirmed_"):
            del st.session_state[key]


# ---------------------------------------------------------------------------
# 1.  Sidebar – choose template
# ---------------------------------------------------------------------------

with st.sidebar:
    st.subheader("Select Template")
    template_files = sorted(p.name for p in TEMPLATES_DIR.glob("*.json"))
    selected_file = st.selectbox(
        "Template JSON",
        options=template_files,
        index=template_files.index(st.session_state.get("selected_template_file"))
        if st.session_state.get("selected_template_file") in template_files
        else 0
        if template_files
        else None,
    )

    template_obj: Template | None = None
    if selected_file:
        st.session_state["selected_template_file"] = selected_file
        raw_template = json.loads((TEMPLATES_DIR / selected_file).read_text())
        try:
            template_obj = Template.model_validate(raw_template)
        except ValidationError as err:
            st.error(f"Template invalid:\n{err}")
            st.stop()
            
        st.session_state["template"] = raw_template

        # If user switched templates, rebuild steps & clear confirmations
        if st.session_state.get("template_name") != template_obj.template_name:
            reset_layer_confirmations()
            set_steps_from_template(
                [layer.model_dump() for layer in template_obj.layers]
            )
            st.session_state["template_name"] = template_obj.template_name

        st.success(f"Loaded: {template_obj.template_name}")

# ---------------------------------------------------------------------------
# 2.  Sidebar – progress indicator
# ---------------------------------------------------------------------------

progress_box = st.sidebar.empty()
render_progress(progress_box)

# ---------------------------------------------------------------------------
# 3.  Upload client data file
# ---------------------------------------------------------------------------

uploaded_file = st.file_uploader(
    "Upload client data file (Excel or CSV)",
    type=["csv", "xls", "xlsx"],
    key="upload_data_file",
)
if uploaded_file:
    st.session_state["uploaded_file"] = uploaded_file

# ---------------------------------------------------------------------------
# 4.  Main wizard
# ---------------------------------------------------------------------------

if st.session_state.get("uploaded_file") and template_obj:
    # Iterate through layers in order
    for idx, layer in enumerate(template_obj.layers):
        layer_flag = f"layer_confirmed_{idx}"
        if not st.session_state.get(layer_flag):

            if layer.type == "header":
                from pages.steps import header as header_step

                header_step.render(layer, idx)

            elif layer.type == "lookup":
                from pages.steps import lookup as lookup_step

                lookup_step.render(layer, idx)

            elif layer.type == "computed":
                from pages.steps import computed as computed_step

                computed_step.render(layer, idx)

            else:
                st.error(f"Unsupported layer type: {layer.type}")
                st.stop()

            # Each layer page is expected to either set layer_confirmed_<idx>
            # and call st.rerun(), or stop execution.
            st.stop()

    # If we reach here, all layers are confirmed
    st.success(
        "✅ All layers confirmed! You can now download the mapping or run the export."
    )

else:
    if not template_obj:
        st.info("Please select a template to begin.")
    elif not st.session_state.get("uploaded_file"):
        st.info("Please upload a client data file to continue.")
