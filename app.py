"""
AI Mapping Agent – Streamlit entrypoint
--------------------------------------

Key features
• Loads a JSON template (v2 schema) and builds wizard steps dynamically
  from its `layers` array.
• Validates the template with Pydantic (strict: no v1 accepted).
• Lets the user upload a client Excel/CSV file.
• Walks through each layer (header → lookup → computed → …),
  setting st.session_state["layer_confirmed_<idx>"] = True
  when a layer is completed.
• Shows a sidebar progress tracker via app_utils.ui_utils.

"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
from pydantic import ValidationError

from auth import require_login, logout_button
from schemas.template_v2 import Template
from app_utils.ui_utils import render_progress, set_steps_from_template
from app_utils.excel_utils import list_sheets, read_tabular_file
from app_utils.postprocess_runner import run_postprocess_if_configured


# ---------------------------------------------------------------------------
# 0. Page config & helpers
# ---------------------------------------------------------------------------
@require_login
def main():
    st.set_page_config(page_title="AI Mapping Agent", layout="wide")
    st.title("AI Mapping Agent")

    if st.session_state.get("unsaved_changes"):
        st.warning(
            "You have unsaved template changes. Use the Template Manager to save them."
        )

    TEMPLATES_DIR = Path("templates")
    TEMPLATES_DIR.mkdir(exist_ok=True)

    def reset_layer_confirmations() -> None:
        """Remove all layer_confirmed_* flags from session state."""
        for k in list(st.session_state.keys()):
            if k.startswith("layer_confirmed_"):
                del st.session_state[k]

    # ---------------------------------------------------------------------------
    # 1. Sidebar – choose template
    # ---------------------------------------------------------------------------

    with st.sidebar:
        st.subheader("Select Template")
        template_files = sorted(p.name for p in TEMPLATES_DIR.glob("*.json"))

        selected_file = st.selectbox(
            "Template JSON",
            options=template_files,
            index=(
                template_files.index(st.session_state.get("selected_template_file"))
                if st.session_state.get("selected_template_file") in template_files
                else 0 if template_files else None
            ),
        )

        template_obj: Template | None = None
        if selected_file:
            st.session_state["selected_template_file"] = selected_file
            with st.spinner("Loading template..."):
                raw_template = json.loads((TEMPLATES_DIR / selected_file).read_text())
                try:
                    template_obj = Template.model_validate(raw_template)
                except ValidationError as err:
                    st.error(f"Template invalid:\n{err}")
                    st.stop()

            # keep raw dict in session for child pages
            st.session_state["template"] = raw_template

            # If user switched templates, rebuild steps & clear confirmations
            if st.session_state.get("template_name") != template_obj.template_name:
                reset_layer_confirmations()
                set_steps_from_template(
                    [layer.model_dump() for layer in template_obj.layers]
                )
                st.session_state["template_name"] = template_obj.template_name
                st.session_state["current_template"] = template_obj.template_name

            st.success(f"Loaded: {template_obj.template_name}")

    # ---------------------------------------------------------------------------
    # 2. Sidebar – progress indicator
    # ---------------------------------------------------------------------------

    progress_box = st.sidebar.empty()
    render_progress(progress_box)

    # def do_reset() -> None:
    #     """Clear uploaded file and mapping progress."""
    #     for k in list(st.session_state.keys()):
    #         if k.startswith("layer_confirmed_"):
    #             st.session_state.pop(k)
    #     for k in [
    #         "uploaded_file",
    #         "upload_data_file",
    #         "template",
    #         "template_name",
    #         "selected_template_file",
    #         "current_template",
    #         "auto_computed_confirm",
    #     ]:
    #         st.session_state.pop(k, None)
    #     st.session_state["current_step"] = 0
    #     st.rerun()

    # st.button("Reset", on_click=do_reset)

    # ---------------------------------------------------------------------------
    # 3. Upload client data file
    # ---------------------------------------------------------------------------

    uploaded_file = st.file_uploader(
        "Upload client data file (Excel or CSV)",
        type=["csv", "xls", "xlsx"],
        key="upload_data_file",
    )
    if uploaded_file:
        st.session_state["uploaded_file"] = uploaded_file
        with st.spinner("Reading file..."):
            sheets = list_sheets(uploaded_file)
        sheet_key = "upload_sheet"
        if len(sheets) > 1:
            st.selectbox("Select sheet", sheets, key=sheet_key)
        else:
            st.session_state[sheet_key] = sheets[0]

    # ---------------------------------------------------------------------------
    # 4. Main wizard
    # ---------------------------------------------------------------------------

    if st.session_state.get("uploaded_file") and template_obj:
        for idx, layer in enumerate(template_obj.layers):
            layer_flag = f"layer_confirmed_{idx}"

            # Auto-confirm computed layer if header page already handled it
            if (
                layer.type == "computed"
                and st.session_state.get("auto_computed_confirm")
                and not st.session_state.get(layer_flag)
            ):
                st.session_state[layer_flag] = True
                continue

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

                # Each layer page should set layer_confirmed_<idx> then rerun,
                # so halt execution after rendering the current step.
                st.stop()

        # All layers confirmed
        st.success(
            "✅ All layers confirmed! You can now download the mapping or run the export."
        )

        if template_obj.postprocess:
            if st.button("Run Postprocess"):
                with st.spinner("Running postprocess..."):
                    sheet = st.session_state.get("upload_sheet", 0)
                    df, _ = read_tabular_file(st.session_state["uploaded_file"], sheet_name=sheet)
                    run_postprocess_if_configured(template_obj, df)
                    st.success("Postprocess complete")

    else:
        if not template_obj:
            st.info("Please select a template to begin.")
        elif not st.session_state.get("uploaded_file"):
            st.info("Please upload a client data file to continue.")
            
    # ---------------------------------------------------------------------------
    # 5. Reset Button
    # ---------------------------------------------------------------------------
            
    def do_reset() -> None:
        """Clear uploaded file and mapping progress."""
        for k in list(st.session_state.keys()):
            if k.startswith("layer_confirmed_"):
                st.session_state.pop(k)
        for k in [
            "uploaded_file",
            "upload_data_file",
            "template",
            "template_name",
            "selected_template_file",
            "current_template",
            "auto_computed_confirm",
        ]:
            st.session_state.pop(k, None)
        st.session_state["current_step"] = 0
        st.rerun()

    st.button("Reset", on_click=do_reset)

main()
logout_button()
