"""
formula_dialog.py
-----------------
Modal dialog for building expressions:

• Clickable “pills” for each column and for operators ( + − × ÷ ( ) ).
• Free-form text area – user can type or click pills.
• Live-preview of first 5 computed rows.
• Saves expression into session state under RETURN_KEY_TEMPLATE.format(key).
"""

from __future__ import annotations
import streamlit as st
import pandas as pd

OPS = ["+", "-", "*", "/", "(", ")"]
RETURN_KEY_TEMPLATE = "formula_expr_{key}"


def open_formula_dialog(df: pd.DataFrame, dialog_key: str) -> None:
    """
    Opens modal dialog.  On Save, writes the expression string to
    st.session_state[RETURN_KEY_TEMPLATE.format(key=dialog_key)].
    """

    result_key = RETURN_KEY_TEMPLATE.format(key=dialog_key)
    expr_key = f"{dialog_key}_expr_text"

    @st.dialog(f"Build Formula for '{dialog_key}'", width="large")
    def _dialog():
        # Initialize stored text if missing
        if expr_key not in st.session_state:
            st.session_state[expr_key] = ""

        st.markdown("##### Click pills or type directly:")

        # --- Pills row: one pill per column, then operator pills ---
        pills = list(df.columns) + OPS
        pill_cols = st.columns(len(pills))
        for i, tok in enumerate(pills):
            if pill_cols[i].button(tok, key=f"pill_{dialog_key}_{tok}"):
                # Append either column reference or raw operator
                if tok in df.columns:
                    st.session_state[expr_key] += f"df['{tok}']"
                else:
                    st.session_state[expr_key] += tok

        # --- Free-form text area -------------------------------------------
        st.text_area(
            "Formula",
            value=st.session_state[expr_key],
            key=expr_key,
            height=100,
        )

        # --- Live preview --------------------------------------------------
        expr = st.session_state[expr_key].strip()
        if expr:
            try:
                # Evaluate in sandboxed locals
                preview = pd.DataFrame({"Result": eval(expr, {"df": df})}).head()
                st.dataframe(preview, use_container_width=True)
                valid = True
            except Exception as e:
                st.error(f"❌ {e}")
                valid = False
        else:
            st.info("Start typing or click a pill above to build your formula.")
            valid = False

        # --- Action buttons ------------------------------------------------
        c1, c2, c3 = st.columns([1,1,1])
        if c1.button("⟲ Clear"):
            st.session_state[expr_key] = ""
            st.rerun()
        # Spacer column hides the middle
        if c3.button("💾 Save", disabled=not valid):
            st.session_state[result_key] = expr
            # Close dialog by rerunning outer script without recalling _dialog
            st.rerun()

    # Immediately invoke the dialog function to show modal
    _dialog()
