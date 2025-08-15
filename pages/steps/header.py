from __future__ import annotations
"""Header mapping step with dynamic field and layer controls."""
import pandas as pd
import streamlit as st
from pathlib import Path
from schemas.template_v2 import FieldSpec, Template
from app_utils.excel_utils import read_tabular_file, save_mapped_csv
from app_utils.mapping_utils import suggest_header_mapping
from app_utils.suggestion_store import get_suggestions, add_suggestion
import re
from app_utils.mapping.header_layer import apply_gpt_header_fallback
from app_utils.mapping.exporter import build_output_template
from app_utils.ui.formula_dialog import open_formula_dialog, RETURN_KEY_TEMPLATE
from app_utils.ui.header_utils import (
    set_field_mapping,
    remove_field,
    add_field,
    remove_formula,
    persist_suggestions_from_mapping,
)
from app_utils.ui_utils import set_steps_from_template
import uuid
import hashlib

st.markdown(
    """
    <style>
    .confidence-badge{font-size:0.75rem;color:#666;background:#eee;border-radius:4px;padding:2px 6px;margin-left:4px;}
    .stSelectbox select{max-width:150px;}
    .stButton>button{padding:.15rem .5rem;}
    .expr-pill{background:#eee;border-radius:12px;padding:2px 8px;font-family:monospace;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Main render function ─────────────────────────────────────────────
def render(layer, idx: int) -> None:
    st.header("Step 1 – Map Source Columns to Template Fields")

    sheet_name = getattr(layer, "sheet", None) or st.session_state.get(
        "upload_sheet", 0
    )
    sheets = st.session_state.get("upload_sheets", [sheet_name])

    df = None
    source_cols: list[str] | None = None
    with st.spinner("Loading file..."):
        for candidate in [sheet_name] + [s for s in sheets if s != sheet_name]:
            try:
                df, source_cols = read_tabular_file(
                    st.session_state["uploaded_file"], sheet_name=candidate
                )
                sheet_name = candidate
                break
            except Exception:  # noqa: BLE001
                continue

    if df is None or source_cols is None:
        st.warning(
            "Sheet could not be read. Please select a different sheet from the dropdown."
        )
        return

    if sheet_name != st.session_state.get("upload_sheet"):
        st.session_state["upload_sheet"] = sheet_name

    required_keys = [f.key for f in layer.fields if f.required]
    adhoc_keys = [f.key for f in layer.fields if f.key.startswith("ADHOC_INFO")]
    optional_keys = [f.key for f in layer.fields if not f.required]
    map_key = f"header_mapping_{idx}"
    sheet_key = f"header_sheet_{idx}"
    cols_key = f"header_cols_{idx}"
    cols_hash = hashlib.sha256("|".join(source_cols).encode()).hexdigest()
    if (
        map_key not in st.session_state
        or st.session_state.get(sheet_key) != sheet_name
        or st.session_state.get(cols_key) != cols_hash
    ):
        auto = suggest_header_mapping([f.key for f in layer.fields], source_cols)
        for k in adhoc_keys:
            auto[k] = {}
        st.session_state[map_key] = auto
        st.session_state[sheet_key] = sheet_name
        st.session_state[cols_key] = cols_hash
        st.session_state.pop(f"header_ai_done_{idx}", None)
    else:
        st.session_state[cols_key] = cols_hash
    mapping = st.session_state[map_key]

    # List of user-added fields
    extra_key = f"header_extra_fields_{idx}"
    extra_fields: list[str] = st.session_state.setdefault(extra_key, [])

    for k, v in list(mapping.items()):
        if isinstance(v, str):
            mapping[k] = {"src": v}

    for field in layer.fields:  # type: ignore
        key = field.key
        for s in get_suggestions(
            st.session_state["current_template"], key, headers=source_cols
        ):
            if s["type"] == "direct":
                for col in source_cols:
                    if col.lower() == s["columns"][0].lower():
                        mapping[key] = {"src": col, "confidence": 1.0}
                        break
                if mapping.get(key):
                    break
            else:  # formula suggestion
                mapping[key] = {
                    "expr": s["formula"],
                    "expr_display": s["display"],
                }

    ai_flag = f"header_ai_done_{idx}"
    if not st.session_state.get(ai_flag):
        before = mapping.copy()
        with st.spinner("Querying GPT..."):
            mapping = apply_gpt_header_fallback(
                mapping, source_cols, targets=required_keys
            )
        st.session_state[map_key] = mapping
        st.session_state[ai_flag] = True
        if mapping != before:
            st.rerun()

    st.caption("• ✅ mapped  • 🛈 suggested  • ❌ required & missing")

    all_fields = list(layer.fields) + [FieldSpec(key=f) for f in extra_fields]
    adhoc_labels = st.session_state.setdefault("header_adhoc_headers", {})
    adhoc_autogen = st.session_state.setdefault("header_adhoc_autogen", {})
    for field in all_fields:  # type: ignore
        key, required = field.key, field.required
        # Source | ⚙ | Expr | Template | Status | 🗑️
        row = st.columns([3, 1, 4, 3, 1, 1])

        # ── Source dropdown ──────────────────────────────────────────────
        src_val = mapping.get(key, {}).get("src", "")
        new_src = row[0].selectbox(
            f"src_{key}",
            options=[""] + source_cols,
            index=([""] + source_cols).index(src_val) if src_val in source_cols else 0,
            key=f"src_{key}",
            label_visibility="collapsed",
        )
        if new_src:
            set_field_mapping(key, idx, {"src": new_src})  # user override
            add_suggestion(
                {
                    "template": st.session_state["current_template"],
                    "field": key,
                    "type": "direct",
                    "formula": None,
                    "columns": [new_src],
                    "display": new_src,
                },
                headers=source_cols,
            )
            if key.startswith("ADHOC_INFO") and new_src != src_val:
                match = re.findall(r"\d+", key)
                default = f"AdHoc{match[0] if match else ''}"
                label = adhoc_labels.get(key, default)
                auto = adhoc_autogen.get(key, True)
                if auto or label == src_val:
                    adhoc_labels[key] = new_src
                    adhoc_autogen[key] = True
                    st.session_state[f"adhoc_label_{key}"] = new_src
        elif "src" in mapping.get(key, {}):
            set_field_mapping(key, idx, {})

        # ── Gear button (Formula builder) ───────────────────────────────
        if row[1].button("⚙️", key=f"calc_{key}", help="Formula builder"):
            open_formula_dialog(df, key)

        # grab dialog save output
        res_key = RETURN_KEY_TEMPLATE.format(key=key)
        res_disp_key = f"{res_key}_display"
        if res_key in st.session_state:
            expr = st.session_state.pop(res_key)
            display = st.session_state.pop(res_disp_key, "")
            set_field_mapping(key, idx, {"expr": expr, "expr_display": display})
            add_suggestion(
                {
                    "template": st.session_state["current_template"],
                    "field": key,
                    "type": "formula",
                    "formula": expr,
                    "columns": [],
                    "display": display or expr,
                },
                headers=source_cols,
            )

        # ── Expression / confidence cell ────────────────────────────────
        expr_disp = mapping.get(key, {}).get("expr_display") or mapping.get(key, {}).get("expr")
        conf = mapping.get(key, {}).get("confidence")
        if expr_disp:
            pill = row[2].columns([4, 1])
            pill[0].markdown(f"<span class='expr-pill'>{expr_disp}</span>", unsafe_allow_html=True)
            if pill[1].button("×", key=f"rm_expr_{key}", help="Remove formula"):
                remove_formula(key, idx)
                st.rerun()
        elif conf is not None and "src" in mapping.get(key, {}):
            pct = int(round(conf * 100))
            row[2].markdown(
                f"<span class='confidence-badge'>🛈 {pct}%</span>",
                unsafe_allow_html=True,
            )
        else:
            row[2].markdown("")

        # ── Template label & optional display name ──────────────────────
        if key.startswith("ADHOC_INFO"):
            sub = row[3].columns([1, 1])
            sub[0].markdown(f"**{key}**")
            match = re.findall(r"\d+", key)
            default = f"AdHoc{match[0] if match else ''}"
            label = adhoc_labels.setdefault(key, default)
            adhoc_autogen.setdefault(key, True)
            val = sub[1].text_input(
                f"adhoc_label_{key}",
                value=label,
                label_visibility="collapsed",
            )
            if val != label:
                adhoc_autogen[key] = False
            adhoc_labels[key] = val or default
        else:
            row[3].markdown(f"**{key}**")

        status = (
            "✅"
            if "src" in mapping.get(key, {})
            else (
                "⚙️"
                if "expr" in mapping.get(key, {})
                else ("🛈" if conf is not None else "❌" if required else "—")
            )
        )
        row[4].markdown(status)

        # ── Delete button for user-added fields ────────────────────────
        if key in extra_fields:
            if row[5].button("🗑️", key=f"del_{key}", help="Remove field"):
                remove_field(key, idx)
                st.rerun()
        else:
            row[5].markdown("")

    st.session_state[map_key] = mapping  # persist any edits

    # Add field row (appears below mapping table)
    add_row = st.columns([3, 1, 4, 3, 1, 1])
    if st.session_state.get(f"adding_field_{idx}"):
        with add_row[3].form(f"add_field_form_{idx}", clear_on_submit=True):
            new_name = st.text_input("New column name", key=f"new_field_{idx}")
            submitted = st.form_submit_button("Add")
        if submitted and new_name:
            add_field(new_name, idx)
            st.session_state[f"adding_field_{idx}"] = False
            st.rerun()
    else:
        if add_row[3].button("+ Add field", key=f"add_field_btn_{idx}"):
            st.session_state[f"adding_field_{idx}"] = True
            st.rerun()

    ready = all(
        (
            (
                ("src" in mapping.get(f.key, {}) and mapping[f.key]["src"])
                or ("expr" in mapping.get(f.key, {}))
            )
            if f.required
            else True
        )
        for f in layer.fields  # type: ignore
    )
    if st.button("Confirm Header Mapping", disabled=not ready, key=f"confirm_{idx}", type="primary"):
        persist_suggestions_from_mapping(layer, mapping, source_cols)
        st.session_state[f"layer_confirmed_{idx}"] = True
        st.rerun()

    # Offer mapped CSV download for current state
    try:
        tpl_raw = st.session_state.get("template")
        if tpl_raw is not None:
            tpl_obj = Template.model_validate(tpl_raw)
            tpl_json = build_output_template(
                tpl_obj, st.session_state, str(uuid.uuid4())
            )
            import tempfile

            with tempfile.NamedTemporaryFile(
                suffix=".csv", delete=False
            ) as tmp:
                tmp_path = Path(tmp.name)
                save_mapped_csv(df, tpl_json, tmp_path)

            csv_bytes = tmp_path.read_bytes()
            tmp_path.unlink()
            st.download_button(
                "Download mapped CSV",
                data=csv_bytes,
                file_name="mapped.csv",
                mime="text/csv",
                key=f"download_mapped_{idx}",
            )
    except Exception:  # noqa: BLE001
        pass
