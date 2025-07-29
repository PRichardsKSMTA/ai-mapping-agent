import json
import os
from datetime import datetime
from typing import List

import streamlit as st
from pydantic import ValidationError

from auth import require_employee
from schemas.template_v2 import Template
from app_utils.excel_utils import list_sheets, read_tabular_file
from app_utils.template_builder import (
    build_header_template,
    build_lookup_layer,
    build_computed_layer,
    build_template,
    load_template_json,
    save_template_file,
    slugify,
    apply_field_choices,
    gpt_field_suggestions,
)
from app_utils.ui_utils import render_progress, compute_current_step


def persist_template(tpl: dict) -> str:
    """Save template and reset unsaved flag."""
    name = save_template_file(tpl)
    st.session_state["unsaved_changes"] = False
    return name


def render_sidebar_columns(columns: List[str]) -> None:
    """Display detected columns in the sidebar."""
    st.sidebar.subheader("Detected Columns")
    if not columns:
        st.sidebar.info("No columns detected yet.")
        return
    for col in columns:
        st.sidebar.write(col)


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

    uploaded = st.file_uploader(
        "Upload CSV/Excel sample or Template JSON",
        type=["csv", "xls", "xlsx", "xlsm", "json"],
        key="tm_file",
    )
    if uploaded is not None:
        if uploaded.name.lower().endswith(".json"):
            try:
                tpl = load_template_json(uploaded)
                safe = persist_template(tpl)
                st.success(f"Saved template '{safe}'")
                st.rerun()
            except ValidationError as err:
                st.error(f"Invalid template: {err}")
            except Exception as e:  # noqa: BLE001
                st.error(f"Failed to read JSON: {e}")
        else:
            st.text_input("Template Name", key="tm_name")
            with st.spinner("Loading file..."):
                sheets = list_sheets(uploaded)
            sheet_key = "tm_sheet"
            if len(sheets) > 1:
                sheet = st.selectbox("Select sheet", sheets, key=sheet_key)
            else:
                sheet = sheets[0]
                st.session_state[sheet_key] = sheet
            with st.spinner("Reading columns..."):
                _, cols = read_tabular_file(uploaded, sheet_name=sheet)
            st.session_state["tm_columns"] = cols
    columns = st.session_state.get("tm_columns", [])
    render_sidebar_columns(columns)
    selections = st.session_state.get("tm_field_select", {})
    required = st.session_state.get("tm_required", {})
    if columns:
        st.subheader("Select fields")
        if st.button("Suggest required fields"):
            if uploaded is None:
                st.error("Please upload a sample file first.")
            else:
                try:
                    sheet = st.session_state.get("tm_sheet", 0)
                    with st.spinner("Analyzing sample..."):
                        df, _ = read_tabular_file(uploaded, sheet_name=sheet)
                        suggestions = gpt_field_suggestions(df)
                    selections.update(suggestions)
                    required = {
                        c: suggestions.get(c) == "required" for c in columns if suggestions.get(c) != "omit"
                    }
                    st.session_state["tm_field_select"] = selections
                    st.session_state["tm_required"] = required
                    st.rerun()
                except Exception as err:  # noqa: BLE001
                    st.error(str(err))
        for col in columns:
            default = selections.get(
                col,
                "required" if required.get(col, False) else "optional",
            )
            choice = st.radio(
                col,
                ["optional", "required", "omit"],
                index=["optional", "required", "omit"].index(default),
                horizontal=True,
                key=f"tm_sel_{col}",
            )
            selections[col] = choice
        st.session_state["tm_field_select"] = selections
        st.session_state["tm_required"] = {
            c: selections.get(c) == "required" for c in columns if selections.get(c) != "omit"
        }

    if columns:
        st.caption(
            "Optional instructions to run after mapping. See `docs/template_spec.md#3.4` for supported actions."
        )
        st.text_area(
            "Postprocess JSON (optional)",
            key="tm_postprocess",
            height=200,
            placeholder='{"type": "sql_insert", "table": "dbo.OUT"}',
        )

        extra_layers = st.session_state.setdefault("tm_extra_layers", [])

        st.subheader("Add Lookup Layer")
        lcol1, lcol2 = st.columns([1, 1])
        src = lcol1.selectbox(
            "Source column",
            options=[""] + columns,
            key="tm_lookup_src",
        )
        tgt = lcol1.text_input("Target field", key="tm_lookup_tgt")
        dsh = lcol2.text_input("Dictionary sheet", key="tm_lookup_dict")
        lsheet = lcol2.text_input(
            "Sheet (optional)", key="tm_lookup_sheet", placeholder="Sheet1"
        )
        if st.button("Add Lookup Layer") and src and tgt and dsh:
            extra_layers.append(
                build_lookup_layer(src, tgt, dsh, sheet=lsheet or None)
            )
            st.session_state["tm_lookup_src"] = ""
            st.session_state["tm_lookup_tgt"] = ""
            st.session_state["tm_lookup_dict"] = ""
            st.session_state["tm_lookup_sheet"] = ""
            st.session_state["unsaved_changes"] = True

        st.subheader("Add Computed Layer")
        ccol1, ccol2 = st.columns([1, 1])
        ctgt = ccol1.text_input("Computed target", key="tm_comp_tgt")
        expr = ccol1.text_input("Expression", key="tm_comp_expr")
        csheet = ccol2.text_input(
            "Sheet (optional)", key="tm_comp_sheet", placeholder="Sheet1"
        )
        if st.button("Add Computed Layer") and ctgt and expr:
            extra_layers.append(
                build_computed_layer(ctgt, expr, sheet=csheet or None)
            )
            st.session_state["tm_comp_tgt"] = ""
            st.session_state["tm_comp_expr"] = ""
            st.session_state["tm_comp_sheet"] = ""
            st.session_state["unsaved_changes"] = True

        if extra_layers:
            st.markdown("**Additional layers:**")
            for i, l in enumerate(extra_layers):
                st.json(l)
                if st.button("Remove", key=f"rm_layer_{i}"):
                    extra_layers.pop(i)
                    st.session_state["tm_extra_layers"] = extra_layers
                    st.session_state["unsaved_changes"] = True
                    st.rerun()

    name = st.session_state.get("tm_name", "")

    if st.button("Save Template", disabled=not (name and columns)):
        selected_cols, req_map = apply_field_choices(columns, selections)
        post_txt = st.session_state.get("tm_postprocess", "").strip()
        post_obj = json.loads(post_txt) if post_txt else None
        header_only = build_header_template(name, selected_cols, req_map)
        all_layers = [header_only["layers"][0]] + st.session_state.get("tm_extra_layers", [])
        tpl = build_template(name, all_layers, post_obj)
        with st.spinner("Saving template..."):
            try:
                Template.model_validate(tpl)
            except ValidationError as err:  # noqa: F841
                st.error(f"Invalid template: {err}")
            else:
                safe = persist_template(tpl)
                st.success(f"Saved template '{safe}'")
                st.session_state.pop("tm_columns", None)
                st.session_state.pop("tm_required", None)
                st.session_state.pop("tm_field_select", None)
                st.session_state.pop("tm_sheet", None)
                st.session_state.pop("tm_extra_layers", None)
                st.rerun()

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
        modified = datetime.fromtimestamp(os.path.getmtime(path)).strftime(
            "%Y-%m-%d %H:%M"
        )
        layers = len(data.get("layers", []))
        row = st.columns([3, 1, 2, 1])
        if row[0].button(data.get("template_name", tf[:-5]), key=f"tm_open_{tf}"):
            edit_template(tf, data)
        row[1].write(f"{layers} layers")
        row[2].write(modified)
        if row[3].button("Delete", key=f"tm_del_{tf}"):
            confirm_delete(tf)


def edit_template(filename: str, data: dict) -> None:
    key = f"edit_{filename}"
    st.session_state.setdefault(key, json.dumps(data, indent=2))
    post_key = f"{key}_post"
    st.session_state.setdefault(
        post_key,
        json.dumps(data.get("postprocess", ""), indent=2)
        if data.get("postprocess") is not None
        else "",
    )

    @st.dialog(f"Edit Template '{filename}'", width="large")
    def _dlg() -> None:
        st.text_area("Template JSON", key, height=400)
        st.caption(
            "Optional instructions to run after mapping. See `docs/template_spec.md#3.4` for details."
        )
        st.text_area("Postprocess JSON (optional)", post_key, height=200)
        c1, c2 = st.columns([1, 1])
        if c1.button("Save", key=f"{key}_save"):
            with st.spinner("Saving template..."):
                try:
                    obj = json.loads(st.session_state[key])
                    post_txt = st.session_state[post_key].strip()
                    post_obj = json.loads(post_txt) if post_txt else None
                    if post_obj is None:
                        obj.pop("postprocess", None)
                    else:
                        obj["postprocess"] = post_obj
                    Template.model_validate(obj)
                    safe = slugify(obj["template_name"])
                    with open(os.path.join("templates", f"{safe}.json"), "w") as f:
                        json.dump(obj, f, indent=2)
                    if safe + ".json" != filename:
                        os.remove(os.path.join("templates", filename))
                    st.success("Template saved")
                    st.session_state["unsaved_changes"] = False
                    st.session_state.pop(key, None)
                    st.rerun()
                except Exception as err:  # noqa: BLE001
                    st.error(f"❌ {err}")
        if c2.button("Cancel", key=f"{key}_cancel"):
            st.session_state.pop(key, None)
            st.rerun()

    _dlg()


def confirm_delete(filename: str) -> None:
    @st.dialog("Confirm Delete", width="small")
    def _dlg() -> None:
        st.warning(f"Delete template '{filename}'?")
        c1, c2 = st.columns([1, 1])
        if c1.button("Delete", key=f"del_{filename}_yes"):
            os.remove(os.path.join("templates", filename))
            st.rerun()
        if c2.button("Cancel", key=f"del_{filename}_no"):
            st.rerun()

    _dlg()


show()
