from __future__ import annotations
"""
Header-mapping step
───────────────────
• Shows friendly formula text (or confidence % for suggestions).
• Writes direct/ formula choices to suggestion_store.
• Auto-suggests from both fuzzy header match **and** past learning.
"""

import streamlit as st
import pandas as pd

from schemas.template_v2 import FieldSpec

from app_utils.excel_utils import read_tabular_file
from app_utils.mapping_utils import suggest_header_mapping
from app_utils.suggestion_store import add_suggestion, get_suggestions
from app_utils.ui.formula_dialog import open_formula_dialog, RETURN_KEY_TEMPLATE


def remove_field(field_key: str, idx: int) -> None:
    """Delete a user-added field from session state."""
    map_key = f"header_mapping_{idx}"
    extra_key = f"header_extra_fields_{idx}"

    mapping = st.session_state.get(map_key, {})
    mapping.pop(field_key, None)
    st.session_state[map_key] = mapping

    extras = st.session_state.get(extra_key, [])
    if field_key in extras:
        extras.remove(field_key)
        st.session_state[extra_key] = extras

# ─── CSS tweaks ───────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .confidence-badge{
        font-size:0.75rem;color:#666;background:#eee;
        border-radius:4px;padding:2px 6px;margin-left:4px;
    }
    .stSelectbox select{max-width:150px;}
    .stButton>button   {padding:.15rem .5rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Main render function ─────────────────────────────────────────────
def render(layer, idx: int) -> None:
    st.header("Step 1 – Map Source Columns to Template Fields")

    # 1⃣  Load client data
    sheet_name = getattr(layer, "sheet", None) or st.session_state.get(
        "upload_sheet", 0
    )
    df, source_cols = read_tabular_file(
        st.session_state["uploaded_file"], sheet_name=sheet_name
    )

    # 2⃣  Build / restore mapping dict (includes confidence from fuzzy match)
    map_key = f"header_mapping_{idx}"
    if map_key not in st.session_state:
        auto = suggest_header_mapping([f.key for f in layer.fields], source_cols)
        # auto = {field_key: {"src": header, "confidence": 0.91}|{}}
        st.session_state[map_key] = auto
    mapping = st.session_state[map_key]

    # List of user-added fields
    extra_key = f"header_extra_fields_{idx}"
    extra_fields: list[str] = st.session_state.setdefault(extra_key, [])
    
    for k, v in list(mapping.items()):
        if isinstance(v, str):
            mapping[k] = {"src": v} 

    # 3⃣  Overlay suggestions learned from previous sessions
    for field in layer.fields:  # type: ignore
        key = field.key
        if mapping.get(key):
            continue  # already has fuzzy suggestion
        for s in get_suggestions(st.session_state["current_template"], key):
            if s["type"] == "direct":
                for col in source_cols:
                    if col.lower() == s["columns"][0].lower():
                        mapping[key] = {"src": col, "confidence": 1.0}
                        break
            else:  # formula suggestion
                mapping[key] = {
                    "expr": s["formula"],
                    "expr_display": s["display"],
                }


    st.caption("• ✅ mapped  • 🛈 suggested  • ❌ required & missing")

    # 4⃣  Render one row per template field (including extras)
    all_fields = list(layer.fields) + [FieldSpec(key=f) for f in extra_fields]
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
            mapping[key] = {"src": new_src}                  # user override
            add_suggestion(                                 # learn it
                {
                    "template": st.session_state["current_template"],
                    "field": key,
                    "type": "direct",
                    "formula": None,
                    "columns": [new_src],
                    "display": new_src,
                }
            )
        elif "src" in mapping.get(key, {}):
            mapping[key] = {}

        # ── Gear button (Formula builder) ───────────────────────────────
        if row[1].button("⚙️", key=f"calc_{key}", help="Formula builder"):
            open_formula_dialog(df, key)

        # grab dialog save output
        res_key = RETURN_KEY_TEMPLATE.format(key=key)
        res_disp_key = f"{res_key}_display"
        if res_key in st.session_state:
            expr = st.session_state.pop(res_key)
            display = st.session_state.pop(res_disp_key, "")
            mapping[key] = {"expr": expr, "expr_display": display}
            add_suggestion(  # store formula learning
                {
                    "template": st.session_state["current_template"],
                    "field": key,
                    "type": "formula",
                    "formula": expr,
                    "columns": [],               # filled by dialog store
                    "display": display or expr,
                }
            )

        # ── Expression / confidence cell ────────────────────────────────
        expr_disp = mapping.get(key, {}).get("expr_display") or mapping.get(key, {}).get("expr")
        conf = mapping.get(key, {}).get("confidence")
        if expr_disp:
            row[2].markdown(f"`{expr_disp}`")
        elif conf is not None and "src" in mapping.get(key, {}):
            pct = int(round(conf * 100))
            row[2].markdown(f"<span class='confidence-badge'>🛈 {pct}%</span>", unsafe_allow_html=True)
        else:
            row[2].markdown("")

        # ── Template label & status icon ────────────────────────────────
        row[3].markdown(f"**{key}**")
        status = (
            "✅" if "src" in mapping.get(key, {}) else
            "⚙️" if "expr" in mapping.get(key, {}) else
            ("🛈" if conf is not None else "❌" if required else "—")
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
            extra_fields.append(new_name)
            mapping[new_name] = {}
            st.session_state[extra_key] = extra_fields
            st.session_state[f"adding_field_{idx}"] = False
            st.rerun()
    else:
        if add_row[3].button("+ Add field", key=f"add_field_btn_{idx}"):
            st.session_state[f"adding_field_{idx}"] = True
            st.rerun()

    # 5⃣  Confirm button
    ready = all(
        (("src" in mapping.get(f.key, {}) and mapping[f.key]["src"]) or ("expr" in mapping.get(f.key, {})))
        if f.required else True
        for f in layer.fields  # type: ignore
    )
    if st.button("Confirm Header Mapping", disabled=not ready, key=f"confirm_{idx}"):
        st.session_state[f"layer_confirmed_{idx}"] = True
        st.session_state["auto_computed_confirm"] = True
        st.rerun()
