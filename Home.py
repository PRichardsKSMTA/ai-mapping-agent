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
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import quote
import streamlit as st
from pydantic import ValidationError
import auth

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency

    def load_dotenv() -> None:
        return None


from auth import require_login, logout_button, get_user_email
from app_utils.user_prefs import get_last_template, set_last_template
from app_utils.azure_sql import (
    fetch_operation_codes,
    fetch_customers,
    get_operational_scac,
    insert_pit_bid_rows,
)
from app_utils import azure_sql
from app_utils.template_builder import slugify
from schemas.template_v2 import Template
from app_utils.ui_utils import (
    render_progress,
    set_steps_from_template,
    compute_current_step,
    render_required_label,
    apply_global_css,
    section_card,
)
from app_utils.excel_utils import (
    list_sheets,
    read_tabular_file,
    save_mapped_csv,
    dedupe_adhoc_headers,
)
from app_utils.postprocess_runner import (
    run_postprocess_if_configured,
    generate_bid_filename,
)
from app_utils.mapping.exporter import build_output_template
from app_utils.ui.header_utils import save_current_template
import uuid

azure_sql._odbc_diag_log()

load_dotenv()


def default_sheet_index(sheets: list[str]) -> int:
    """Return index of first sheet not labeled as instructions."""
    for idx, name in enumerate(sheets):
        if "instruction" not in name.lower():
            return idx
    return 0


def do_reset(user_email: str | None = None) -> None:
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
        "upload_sheet",
        "upload_sheets",
        "template",
        "template_name",
        "selected_template_file",
        "current_template",
        "auto_computed_confirm",
        "export_complete",
        "customer_name",
        "customer_choice",
        "selected_customer",
        "new_customer_name",
        "mapped_preview_df",
    ]:
        st.session_state.pop(k, None)
    old_key = st.session_state.get("upload_data_file_key")
    if old_key:
        st.session_state.pop(old_key, None)
    st.session_state["upload_data_file_key"] = str(uuid.uuid4())
    st.session_state["current_step"] = 0
    st.session_state["postprocess_running"] = False
    if user_email:
        set_last_template(user_email, "")
    st.session_state["_reset_triggered"] = True


# ---------------------------------------------------------------------------
# Helper to remove admin-only pages
# ---------------------------------------------------------------------------
def remove_template_manager_page() -> None:
    """Hide Template Manager page for non-admin users."""
    if st.session_state.get("is_admin"):
        return
    get_pages = getattr(st, "experimental_get_pages", None)
    if not get_pages:
        return
    pages = get_pages()
    pages.pop("pages/Template_Manager.py", None)


# ---------------------------------------------------------------------------
# 0. Page config & helpers
# ---------------------------------------------------------------------------
@require_login
def main():
    remove_template_manager_page()
    st.set_page_config(page_title="AI Mapping Agent", layout="wide")
    apply_global_css()
    st.title("AI Mapping Agent")
    user_email = get_user_email()
    if user_email and hasattr(st, "caption"):
        st.caption(f"Signed in as {user_email}")

    if st.session_state.get("unsaved_changes"):
        st.warning(
            "Unsaved template changes detected. Save before leaving to keep your work."
        )
        st.caption("Template edits exist only in this session until you save them.")
        save_col, mgr_col = st.columns(2)
        save_col.button("Save Template", on_click=save_current_template)
        if st.session_state.get("is_admin"):
            mgr_col.page_link(
                "pages/Template_Manager.py", label="Template Manager", icon="📝"
            )

    TEMPLATES_DIR = Path("templates")
    TEMPLATES_DIR.mkdir(exist_ok=True)

    st.session_state.setdefault("upload_data_file_key", str(uuid.uuid4()))
    st.session_state.setdefault("postprocess_running", False)

    if user_email and "selected_template_file" not in st.session_state:
        last = get_last_template(user_email)
        if last:
            st.session_state["selected_template_file"] = last

    def reset_layer_confirmations() -> None:
        """Remove all layer_confirmed_* flags from session state."""
        for k in list(st.session_state.keys()):
            if k.startswith("layer_confirmed_"):
                del st.session_state[k]

    # ---------------------------------------------------------------------------
    # 1. Sidebar – choose template
    # ---------------------------------------------------------------------------

    with st.sidebar:
        st.subheader("Select Operation Code")
        if user_email is None:
            st.error("Please sign in to select an operation code.")
            return
        try:
            op_codes = fetch_operation_codes(user_email)
        except RuntimeError as err:
            st.error(f"Operation lookup failed: {err}")
            return
        if not op_codes:
            st.error("No operations available.")
            return
        op_idx = 0
        if st.session_state.get("operation_code") in op_codes:
            op_idx = op_codes.index(st.session_state["operation_code"])
        # render_required_label("Operation Code")
        st.selectbox(
            "Operation Code",
            op_codes,
            index=op_idx,
            key="operation_code",
            label_visibility="collapsed",
        )
        st.session_state["operational_scac"] = get_operational_scac(
            st.session_state["operation_code"]
        )

        st.subheader("Select Template")
        template_entries: list[tuple[str, str]] = []
        for path in TEMPLATES_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                name = data.get("template_name")
                if not isinstance(name, str) or not name.strip():
                    raise ValueError
                friendly = name
            except Exception:
                friendly = path.stem
            template_entries.append((path.name, friendly))
        template_entries.sort(key=lambda t: t[1])
        template_files = [fname for fname, _ in template_entries]
        template_names = {fname: label for fname, label in template_entries}
        # render_required_label("Template JSON")
        selected_file = st.selectbox(
            "Template JSON",
            options=template_files,
            index=(
                template_files.index(st.session_state.get("selected_template_file"))
                if st.session_state.get("selected_template_file") in template_files
                else 0 if template_files else None
            ),
            label_visibility="collapsed",
            format_func=lambda f: template_names.get(f, f),
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
    st.sidebar.button(
        "Reset",
        on_click=lambda: do_reset(user_email),
        type="secondary",
        use_container_width=True,
    )
    if st.session_state.pop("_reset_triggered", False):
        st.rerun()

    # ---------------------------------------------------------------------------
    # 3. Upload & sheet selection
    # ---------------------------------------------------------------------------

    with section_card("Upload", ""):
        render_required_label("Upload client data file (Excel or CSV)")
        uploaded_file = st.file_uploader(
            "Upload client data file (Excel or CSV)",
            type=["csv", "xls", "xlsx"],
            key=st.session_state["upload_data_file_key"],
            label_visibility="collapsed",
        )
    if uploaded_file:
        st.session_state["uploaded_file"] = uploaded_file
        with st.spinner("Reading file..."):
            sheets = list_sheets(uploaded_file)
        st.session_state["upload_sheets"] = sheets

    if st.session_state.get("uploaded_file"):
        with section_card("Sheet selection", ""):
            render_required_label("Choose worksheet and preview data")
            sheets = st.session_state.get("upload_sheets", [])
            sheet_key = "upload_sheet"
            default_idx = default_sheet_index(sheets) if sheets else 0
            if len(sheets) > 1:
                try:
                    sheet_col, _ = st.columns([3, 1])
                except TypeError:
                    sheet_col, _ = st.columns(2)
                selectbox_fn = getattr(sheet_col, "selectbox", st.selectbox)
                selectbox_fn(
                    "Select sheet",
                    sheets,
                    index=default_idx,
                    key=sheet_key,
                )
            if sheet_key not in st.session_state and sheets:
                st.session_state[sheet_key] = sheets[default_idx]
            if st.session_state.get("upload_sheet") and hasattr(
                st.session_state["uploaded_file"], "name"
            ):
                df, _ = read_tabular_file(
                    st.session_state["uploaded_file"],
                    sheet_name=st.session_state["upload_sheet"],
                )
                st.caption("Source data preview – first 5 rows")
                st.dataframe(df.head())

    customer_valid = True
    st.session_state.setdefault("customer_ids", [])

    if hasattr(st, "divider"):
        if hasattr(st, "divider"):
            st.divider()
        else:  # pragma: no cover - Streamlit <1.20 or test stubs
            st.markdown("---")

    # ---------------------------------------------------------------------------
    # 4. Customer selection (PIT BID only)
    # ---------------------------------------------------------------------------
    if (
        st.session_state.get("uploaded_file")
        and st.session_state.get("template_name") == "PIT BID"
        and st.session_state.get("operational_scac")
    ):
        with section_card("Customer selection", ""):
            render_required_label("Select Customer and Customer ID")
            scac = st.session_state["operational_scac"]
            if (
                st.session_state.get("customer_options") is None
                or st.session_state.get("customer_scac") != scac
            ):
                try:
                    st.session_state["customer_options"] = fetch_customers(scac)
                    st.session_state["customer_scac"] = scac
                    if (
                        st.session_state["customer_options"]
                        and "CLIENT_SCAC" in st.session_state["customer_options"][0]
                    ):
                        st.session_state["client_scac"] = st.session_state[
                            "customer_options"
                        ][0]["CLIENT_SCAC"]
                except RuntimeError as err:
                    st.error(f"Customer lookup failed: {err}")
                    return
            cust_records = [
                c for c in st.session_state["customer_options"] if c["BILLTO_NAME"]
            ]
            st.session_state["customer_options"] = cust_records
            seen_names: set[str] = set()
            cust_names: list[str] = []
            for c in cust_records:
                name = c["BILLTO_NAME"]
                norm = name.strip().lower()
                if norm not in seen_names:
                    seen_names.add(norm)
                    cust_names.append(name.title())
            if cust_names:
                cust_names.insert(0, "+ New Customer")
                prev_choice = st.session_state.get("customer_choice")
                if (
                    prev_choice is None
                    and st.session_state.get("customer_name") in cust_names
                ):
                    prev_choice = st.session_state["customer_name"]
                    st.session_state["customer_choice"] = prev_choice
                idx = (
                    cust_names.index(prev_choice) if prev_choice in cust_names else None
                )
                try:
                    cust_col, _ = st.columns([3, 1])
                except TypeError:
                    cust_col, _ = st.columns(2)
                selectbox_fn = getattr(cust_col, "selectbox", st.selectbox)
                selected_name = selectbox_fn(
                    "Customer",
                    cust_names,
                    index=idx,
                    key="customer_choice",
                    placeholder="Select a customer",
                )
                if selected_name == "+ New Customer":
                    new_name: str = st.text_input(
                        "Customer Name", key="new_customer_name"
                    )
                    customer_name = new_name.strip() if new_name else ""
                    st.session_state["customer_name"] = customer_name
                    st.session_state["customer_id_options"] = []
                    st.session_state["customer_ids"] = []
                    st.session_state["selected_customer"] = (
                        {"BILLTO_NAME": customer_name} if customer_name else {}
                    )
                else:
                    st.session_state.pop("new_customer_name", None)
                    customer_name = selected_name
                    st.session_state["customer_name"] = customer_name
                    if selected_name and selected_name != prev_choice:
                        st.session_state["customer_ids"] = []
                if customer_name:
                    matches = [
                        c
                        for c in cust_records
                        if c["BILLTO_NAME"].strip().casefold()
                        == customer_name.casefold()
                    ]
                    if matches:
                        st.session_state["selected_customer"] = matches[0]
                        billto_ids: list[str] = [
                            c["BILLTO_ID"]
                            for c in cust_records
                            if c["BILLTO_NAME"].strip().casefold()
                            == customer_name.casefold()
                            and c.get("BILLTO_ID")
                        ]
                        st.session_state["customer_id_options"] = billto_ids
                        if billto_ids:
                            if len(billto_ids) == 1 and not st.session_state.get(
                                "customer_ids"
                            ):
                                st.session_state["customer_ids"] = billto_ids[:1]
                            else:

                                def select_all_ids() -> None:
                                    st.session_state["customer_ids"] = billto_ids[:5]

                                def deselect_all_ids() -> None:
                                    st.session_state["customer_ids"] = []


                                try:
                                    cid_col, _ = st.columns([3, 1])
                                except TypeError:
                                    cid_col, _ = st.columns(2)
                                multiselect_fn = getattr(
                                    cid_col, "multiselect", st.multiselect
                                )
                                multiselect_fn(
                                    "Customer ID",
                                    billto_ids,
                                    key="customer_ids",
                                    max_selections=5,
                                    label_visibility="collapsed",
                                    placeholder="Select Customer ID",
                                )
                                btn1, btn2, _ = cid_col.columns(
                                    [2, 2, 18], gap="small"
                                )
                                btn1.button(
                                    "Select all",
                                    on_click=select_all_ids,
                                    key="cid_select_all",
                                )
                                btn2.button(
                                    "Deselect all",
                                    on_click=deselect_all_ids,
                                    key="cid_clear_all",
                                )
                    else:
                        st.session_state["customer_id_options"] = []
                        st.session_state["customer_ids"] = []
                        st.info("Selected customer has no Customer IDs.")
                else:
                    if st.session_state.get("customer_choice") != "+ New Customer":
                        st.info("Select a customer to view ID options.")
            else:
                st.warning("No customers found for selected operation.")
            if not st.session_state.get("customer_name"):
                st.error("Please select a customer to proceed.")
                customer_valid = False
            else:
                id_opts: list[str] = st.session_state.get("customer_id_options") or []
                customer_choice = st.session_state.get("customer_choice")
                if id_opts and customer_choice != "+ New Customer":
                    if not st.session_state.get("customer_ids"):
                        st.error("Select at least one Customer ID.")
                        customer_valid = False
                else:
                    st.session_state["customer_ids"] = []

    # ---------------------------------------------------------------------------
    # 5. Main wizard
    # ---------------------------------------------------------------------------

    if st.session_state.get("uploaded_file") and template_obj and customer_valid:
        for idx, layer in enumerate(template_obj.layers):
            layer_flag = f"layer_confirmed_{idx}"

            if not st.session_state.get(layer_flag):
                with section_card("Mapping", "Map source data to template fields"):
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
        last_idx = len(template_obj.layers) - 1
        if st.button("Back to mappings"):
            for key in [
                "export_complete",
                "mapped_csv",
                "mapped_preview_df",
            ]:
                st.session_state.pop(key, None)
            st.session_state["postprocess_running"] = False
            st.session_state.pop(f"layer_confirmed_{last_idx}", None)
            st.session_state["current_step"] = compute_current_step()
            st.rerun()

        if hasattr(st, "divider"):
            st.divider()
        else:  # pragma: no cover - Streamlit <1.20 or test stubs
            st.markdown("---")

        if not st.session_state.get("export_complete"):
            header_text: str = "Step — Run Export"
            button_text: str = "Run Export"
            if template_obj.template_name == "PIT BID":
                header_text = "Step 2 - Generate PIT File"
                button_text = "Generate PIT"
            st.header(header_text)

            sheet = st.session_state.get("upload_sheet", 0)
            df, _ = read_tabular_file(
                st.session_state["uploaded_file"], sheet_name=sheet
            )
            preview_guid = str(uuid.uuid4())
            preview_json = build_output_template(
                template_obj, st.session_state, preview_guid
            )
            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                tmp_path = Path(tmp.name)
                mapped_df = save_mapped_csv(df, preview_json, tmp_path)
            tmp_path.unlink()
            adhoc_headers = st.session_state.get("header_adhoc_headers", {})
            adhoc_headers = dedupe_adhoc_headers(
                adhoc_headers,
                [c for c in mapped_df.columns if c not in adhoc_headers],
            )
            st.session_state["header_adhoc_headers"] = adhoc_headers
            display_df = mapped_df.rename(columns=adhoc_headers)
            duplicate_headers: list[str] = (
                display_df.columns[display_df.columns.duplicated()].tolist()
            )
            if duplicate_headers:
                st.error(
                    "Duplicate column names detected: "
                    f"{', '.join(duplicate_headers)}. Please revise your mappings."
                )
            else:
                st.session_state["mapped_preview_df"] = display_df
                st.dataframe(display_df)

            st.markdown(
                """
                <style>
                div[data-testid="stButton"][key="postprocess_run"] > button {
                    background-color: #0d6efd;
                    color: white;
                }
                div[data-testid="stButton"][key="postprocess_run"] > button:hover {
                    background-color: #0b5ed7;
                    color: white;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

            if st.button(
                button_text,
                key="postprocess_run",
                type="primary",
                disabled=st.session_state.get("postprocess_running", False),
            ):
                st.session_state["postprocess_running"] = True
                with st.spinner("Gathering mileage and toll data…"):
                    st.markdown(":blue[You'll receive an email notification when the process is complete...]")
                    preview_payload: dict[str, Any] = azure_sql.get_pit_url_payload(
                        st.session_state["operation_code"]
                    )
                    preview_item = (preview_payload.get("item/In_dtInputData") or [{}])[
                        0
                    ]
                    dest_site: str | None = preview_item.get("CLIENT_DEST_SITE")
                    dest_path: str | None = preview_item.get("CLIENT_DEST_FOLDER_PATH")
                    if dest_site and dest_path:
                        sharepoint_url = (
                            f"{dest_site.rstrip('/')}{quote(dest_path, safe='/')}"
                        )
                        st.link_button("Open SharePoint folder", sharepoint_url)
                    sheet = st.session_state.get("upload_sheet", 0)
                    df, _ = read_tabular_file(
                        st.session_state["uploaded_file"], sheet_name=sheet
                    )
                    guid = str(uuid.uuid4())
                    final_json = build_output_template(
                        template_obj, st.session_state, guid
                    )

                    # Prepare CSV for download using current mappings
                    with tempfile.NamedTemporaryFile(
                        suffix=".csv", delete=False
                    ) as tmp:
                        tmp_path = Path(tmp.name)
                        mapped_df = save_mapped_csv(df, final_json, tmp_path)

                    adhoc_headers = (
                        st.session_state.get("header_adhoc_headers") or {}
                    )
                    insert_pit_bid_rows(
                        mapped_df,
                        st.session_state["operation_code"],
                        st.session_state["customer_name"],
                        st.session_state.get("customer_ids"),
                        guid,
                        adhoc_headers,
                    )
                    bid_filename = generate_bid_filename(
                        st.session_state["operation_code"],
                        st.session_state.get("customer_name", ""),
                    )
                    user_email = auth.ensure_user_email()
                    if user_email:
                        azure_sql.log_mapping_process(
                            guid,
                            st.session_state.get("operation_code"),
                            slugify(template_obj.template_name),
                            template_obj.template_name,
                            user_email,
                            bid_filename,
                            json.dumps(final_json),
                            template_obj.template_guid,
                            adhoc_headers,
                        )
                    else:
                        st.warning("User email missing; export not logged.")
                    logs_post, payload, _ = run_postprocess_if_configured(
                        template_obj,
                        df,
                        guid,
                        st.session_state.get("customer_name", ""),
                        st.session_state.get("operation_code"),
                        user_email=user_email,
                        filename=bid_filename,
                    )
                    csv_bytes = tmp_path.read_bytes()
                    tmp_path.unlink()

                    st.session_state.update(
                        {
                            "export_complete": True,
                            "mapped_csv": csv_bytes,
                            "postprocess_payload": payload,
                        }
                    )
                    st.session_state["postprocess_running"] = False
                    st.rerun()
        else:
            payload: dict[str, Any] = st.session_state.get("postprocess_payload") or {}
            dest_site: str | None = payload.get("CLIENT_DEST_SITE")
            dest_path: str | None = payload.get("CLIENT_DEST_FOLDER_PATH")
            if not (dest_site and dest_path):
                nested = (payload.get("item/In_dtInputData") or [{}])[0]
                dest_site = dest_site or nested.get("CLIENT_DEST_SITE")
                dest_path = dest_path or nested.get("CLIENT_DEST_FOLDER_PATH")
            sharepoint_url: str | None = None
            if dest_site and dest_path:
                sharepoint_url = f"{dest_site.rstrip('/')}{quote(dest_path, safe='/')}"
            preview_df = st.session_state.get("mapped_preview_df")
            if preview_df is not None:
                st.dataframe(preview_df)
            st.success(
                "Your PIT is being created and will be uploaded to your SharePoint site in ~5 minutes."
            )
            if sharepoint_url:
                st.link_button("Open SharePoint folder", sharepoint_url)
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

    st.markdown(
        "<div style='margin-bottom: 240px'></div>",
        unsafe_allow_html=True,
    )


main()
logout_button()
