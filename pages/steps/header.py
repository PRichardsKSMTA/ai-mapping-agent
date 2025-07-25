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

from app_utils.excel_utils import read_tabular_file
from app_utils.mapping_utils import suggest_header_mapping
from app_utils.suggestion_store import add_suggestion, get_suggestions
from app_utils.ui.formula_dialog import open_formula_dialog, RETURN_KEY_TEMPLATE

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
    df, source_cols = read_tabular_file(st.session_state["uploaded_file"])

    # 2⃣  Build / restore mapping dict (includes confidence from fuzzy match)
    map_key = f"header_mapping_{idx}"
    if map_key not in st.session_state:
        auto = suggest_header_mapping([f.key for f in layer.fields], source_cols)
        # auto = {field_key: {"src": header, "confidence": 0.91}|{}}
        st.session_state[map_key] = auto
    mapping = st.session_state[map_key]
    
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

    # 4⃣  Render one row per template field
    for field in layer.fields:  # type: ignore
        key, required = field.key, field.required
        row = st.columns([3, 1, 4, 3, 1])  # Source | ⚙ | Expr | Template | Status

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

    st.session_state[map_key] = mapping  # persist any edits

    # 5⃣  Confirm button
    ready = all(
        (("src" in m and m["src"]) or ("expr" in m)) if f.required else True
        for f, m in zip(layer.fields, mapping.values())  # type: ignore
    )
    if st.button("Confirm Header Mapping", disabled=not ready, key=f"confirm_{idx}"):
        st.session_state[f"layer_confirmed_{idx}"] = True
        st.session_state["auto_computed_confirm"] = True
        st.rerun()
