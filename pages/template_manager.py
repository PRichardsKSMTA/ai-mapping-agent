import json
import os
from datetime import datetime
import streamlit as st
from pydantic import ValidationError

from auth import require_employee
from schemas.template_v2 import Template
from app_utils.excel_utils import read_tabular_file
from app_utils.template_builder import build_header_template
from app_utils.ui_utils import render_progress, compute_current_step


@require_employee
def show() -> None:
    st.title("Template Manager")

    st.session_state["current_step"] = compute_current_step()
    progress_box = st.empty()
    render_progress(progress_box)

    # ------------------------------------------------------------------
    # Create new template from sample file
    # ------------------------------------------------------------------
    st.header("Create New Template")
    name = st.text_input("Template Name", key="tm_name")
    sample = st.file_uploader(
        "Upload Sample CSV or Excel",
        type=["csv", "xls", "xlsx", "xlsm"],
        key="tm_sample",
    )
    if sample is not None:
        _, cols = read_tabular_file(sample)
        st.session_state["tm_columns"] = cols
    columns = st.session_state.get("tm_columns", [])
    required = st.session_state.get("tm_required", {})
    if columns:
        st.subheader("Mark required fields")
        for col in columns:
            required[col] = st.checkbox(col, key=f"tm_req_{col}", value=required.get(col, False))
        st.session_state["tm_required"] = required

    if st.button("Save Template", disabled=not (name and columns)):
        tpl = build_header_template(name, columns, required)
        try:
            Template.model_validate(tpl)
        except ValidationError as err:  # noqa: F841
            st.error(f"Invalid template: {err}")
        else:
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
            os.makedirs("templates", exist_ok=True)
            with open(os.path.join("templates", f"{safe}.json"), "w") as f:
                json.dump(tpl, f, indent=2)
            st.success(f"Saved template '{safe}'")
            st.session_state.pop("tm_columns", None)
            st.session_state.pop("tm_required", None)
            st.rerun()

    st.divider()

    # ------------------------------------------------------------------
    # Upload existing template JSON
    # ------------------------------------------------------------------
    st.header("Upload Template JSON")
    uploaded = st.file_uploader("Upload Template JSON", type=["json"], key="tm_upload")
    if uploaded is not None:
        try:
            raw = json.load(uploaded)
            Template.model_validate(raw)
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in raw["template_name"])
            os.makedirs("templates", exist_ok=True)
            with open(os.path.join("templates", f"{safe}.json"), "w") as f:
                json.dump(raw, f, indent=2)
            st.success(f"Saved template '{safe}'")
            st.rerun()
        except ValidationError as err:
            st.error(f"Invalid template: {err}")
        except Exception as e:  # noqa: BLE001
            st.error(f"Failed to read JSON: {e}")

    st.divider()

    # ------------------------------------------------------------------
    # List existing templates
    # ------------------------------------------------------------------
    st.header("Existing Templates")
    os.makedirs("templates", exist_ok=True)
    tmpl_files = [f for f in os.listdir("templates") if f.endswith(".json")]
    for tf in tmpl_files:
        path = os.path.join("templates", tf)
        with open(path) as f:
            data = json.load(f)
        modified = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")
        layers = len(data.get("layers", []))
        row = st.columns([3, 1, 2, 1])
        if row[0].button(data.get("template_name", tf[:-5]), key=f"tm_open_{tf}"):
            edit_template(tf, data)
        row[1].write(f"{layers} layers")
        row[2].write(modified)
        if row[3].button("Delete", key=f"tm_del_{tf}"):
            os.remove(path)
            st.rerun()


def edit_template(filename: str, data: dict) -> None:
    key = f"edit_{filename}"
    st.session_state.setdefault(key, json.dumps(data, indent=2))

    @st.dialog(f"Edit Template '{filename}'", width="large")
    def _dlg() -> None:
        st.text_area("Template JSON", key, height=400)
        c1, c2 = st.columns(2)
        if c1.button("Save", key=f"{key}_save"):
            try:
                obj = json.loads(st.session_state[key])
                Template.model_validate(obj)
                safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in obj["template_name"])
                with open(os.path.join("templates", f"{safe}.json"), "w") as f:
                    json.dump(obj, f, indent=2)
                if safe + ".json" != filename:
                    os.remove(os.path.join("templates", filename))
                st.success("Template saved")
                st.session_state.pop(key, None)
                st.rerun()
            except Exception as err:  # noqa: BLE001
                st.error(f"❌ {err}")
        if c2.button("Cancel", key=f"{key}_cancel"):
            st.session_state.pop(key, None)
            st.rerun()


show()
