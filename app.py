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
import os
from pathlib import Path

import streamlit as st
from pydantic import ValidationError
from dotenv import load_dotenv

from auth import require_login, logout_button, get_user_email
from app_utils.user_prefs import get_last_template, set_last_template
from app_utils.azure_sql import (
    fetch_operation_codes,
    fetch_customers,
    get_operational_scac,
    insert_pit_bid_rows,
)
from schemas.template_v2 import Template
from app_utils.ui_utils import render_progress, set_steps_from_template
from app_utils.excel_utils import list_sheets, read_tabular_file, save_mapped_csv
from app_utils.postprocess_runner import run_postprocess_if_configured
from app_utils.mapping.exporter import build_output_template
import uuid

load_dotenv()
os.environ.setdefault("ENABLE_POSTPROCESS", st.secrets.get("ENABLE_POSTPROCESS", "0"))


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

    user_email = get_user_email()
    if user_email and "selected_template_file" not in st.session_state:
        last = get_last_template(user_email)
        if last:
            st.session_state["selected_template_file"] = last

    def reset_layer_confirmations() -> None:
        """Remove all layer_confirmed_* flags from session state."""
        for k in list(st.session_state.keys()):
            if k.startswith("layer_confirmed_"):
                del st.session_state[k]

    def do_reset() -> None:
        """Clear uploaded file, mappings, and export state."""
        prefixes = [
            "layer_confirmed_",
            "header_",
            "lookup_",
            "computed_",
        ]
        for k in list(st.session_state.keys()):
            if any(k.startswith(p) for p in prefixes):
                st.session_state.pop(k)
        for k in [
            "uploaded_file",
            "upload_data_file",
            "upload_sheet",
            "upload_sheets",
            "template",
            "template_name",
            "selected_template_file",
            "current_template",
            "auto_computed_confirm",
            "export_complete",
            "export_logs",
            "final_json",
        ]:
            st.session_state.pop(k, None)
        st.session_state["current_step"] = 0
        if user_email:
            set_last_template(user_email, "")
        st.session_state["_reset_triggered"] = True

    # ---------------------------------------------------------------------------
    # 1. Sidebar – choose template
    # ---------------------------------------------------------------------------

    with st.sidebar:
        st.subheader("Select Operation Code")
        try:
            op_codes = fetch_operation_codes()
        except RuntimeError as err:
            st.error(f"Operation lookup failed: {err}")
            return
        if not op_codes:
            st.error("No operations available.")
            return
        op_idx = 0
        if st.session_state.get("operation_code") in op_codes:
            op_idx = op_codes.index(st.session_state["operation_code"])
        st.selectbox("Operation Code:", op_codes, index=op_idx, key="operation_code")
        st.session_state["operational_scac"] = get_operational_scac(
            st.session_state["operation_code"]
        )

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
            if user_email:
                set_last_template(user_email, selected_file)
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
    st.sidebar.button("Reset", on_click=do_reset)
    if st.session_state.pop("_reset_triggered", False):
        st.rerun()

    # ---------------------------------------------------------------------------
    # 3. Customer selection (PIT BID only)
    # ---------------------------------------------------------------------------

    if (
        st.session_state.get("template_name") == "PIT BID"
        and st.session_state.get("operational_scac")
    ):
        scac = st.session_state["operational_scac"]
        if (
            st.session_state.get("customer_options") is None
            or st.session_state.get("customer_scac") != scac
        ):
            try:
                st.session_state["customer_options"] = fetch_customers(scac)
                st.session_state["customer_scac"] = scac
            except RuntimeError as err:
                st.error(f"Customer lookup failed: {err}")
                return
        cust_records = st.session_state["customer_options"]
        cust_names = [c["BILLTO_NAME"] for c in cust_records]
        if cust_names:
            options = [""] + cust_names
            idx = 0
            if st.session_state.get("customer_name") in cust_names:
                idx = cust_names.index(st.session_state["customer_name"]) + 1
            selected_name = st.selectbox(
                "Customer (optional)", options, index=idx, key="customer_name_select"
            )
            if selected_name:
                st.session_state["customer_name"] = selected_name
                st.session_state["selected_customer"] = next(
                    c for c in cust_records if c["BILLTO_NAME"] == selected_name
                )
            else:
                st.session_state["customer_name"] = None
                st.session_state["selected_customer"] = None
        else:
            st.warning("No customers found for selected operation.")

    # ---------------------------------------------------------------------------
    # 4. Upload client data file
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
        st.session_state["upload_sheets"] = sheets
        sheet_key = "upload_sheet"
        if len(sheets) > 1:
            st.selectbox("Select sheet", sheets, key=sheet_key)
        else:
            st.session_state[sheet_key] = sheets[0]

    # ---------------------------------------------------------------------------
    # 5. Main wizard
    # ---------------------------------------------------------------------------

    if st.session_state.get("uploaded_file") and template_obj:
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

                # Each layer page should set layer_confirmed_<idx> then rerun,
                # so halt execution after rendering the current step.
                st.stop()

        # All layers confirmed - run export step
        st.success("✅ All layers confirmed! Proceed to export.")

        if not st.session_state.get("export_complete"):
            st.header("Step — Run Export")
            if st.button("Run Export"):
                with st.spinner("Running postprocess..."):
                    sheet = st.session_state.get("upload_sheet", 0)
                    df, _ = read_tabular_file(
                        st.session_state["uploaded_file"], sheet_name=sheet
                    )
                    guid = str(uuid.uuid4())
                    final_json = build_output_template(
                        template_obj, st.session_state, guid
                    )

                    # Prepare CSV for download using current mappings
                    import tempfile

                    with tempfile.NamedTemporaryFile(
                        suffix=".csv", delete=False
                    ) as tmp:
                        tmp_path = Path(tmp.name)
                        mapped_df = save_mapped_csv(df, final_json, tmp_path)

                    rows = insert_pit_bid_rows(
                        mapped_df,
                        st.session_state["operation_code"],
                        st.session_state.get("customer_name"),
                        guid,
                    )
                    logs = [
                        f"Inserted {rows} rows into RFP_OBJECT_DATA"
                    ]
                    logs_post, payload = run_postprocess_if_configured(
                        template_obj,
                        df,
                        guid,
                        st.session_state.get("operation_code"),
                        st.session_state.get("customer_name"),
                    )
                    logs.extend(logs_post)
                    csv_bytes = tmp_path.read_bytes()
                    tmp_path.unlink()

                    state_updates = {
                        "export_complete": True,
                        "export_logs": logs,
                        "final_json": final_json,
                        "mapped_csv": csv_bytes,
                    }
                    if payload is not None:
                        state_updates["postprocess_payload"] = payload
                    st.session_state.update(state_updates)
                    st.rerun()
        else:
            st.success(
                "Your PIT is being created and will be uploaded to your SharePoint site in ~5 minutes."
            )
            dest_site = os.getenv("CLIENT_DEST_SITE")
            if dest_site:
                st.markdown(
                    f'<a href="{dest_site}" target="_blank">Open SharePoint site</a>',
                    unsafe_allow_html=True,
                )
            for line in st.session_state.get("export_logs", []):
                st.write(line)
            payload: dict[str, object] | None = st.session_state.get(
                "postprocess_payload"
            )
            if payload is not None:
                if template_obj.postprocess:
                    st.write(template_obj.postprocess.url)
                st.json(payload)
            st.json(st.session_state.get("final_json"))
            csv_data = st.session_state.get("mapped_csv")
            if csv_data:
                st.download_button(
                    "Download mapped CSV",
                    data=csv_data,
                    file_name="mapped.csv",
                    mime="text/csv",
                )

    else:
        if not template_obj:
            st.info("Please select a template to begin.")
        elif not st.session_state.get("uploaded_file"):
            st.info("Please upload a client data file to continue.")
main()
logout_button()
