"""
expression_builder.py
---------------------
Dynamic Expression Builder supporting N operands, N−1 operators, and
parentheses—all inline inside a @st.dialog.

• Operands chosen from dataframe columns.
• Operators: + − × ÷.
• Parentheses: ( and ).
• “Add operand” simply mutates session_state; no st.rerun() here.
• Live preview on first 5 rows.
• Returns (expression_string, valid_flag).

Usage in a dialog:
    expr, valid = build_expression(df, key_prefix="net_change")
"""

from __future__ import annotations
import streamlit as st
import pandas as pd
from typing import List, Tuple

OPS = {"+": "+", "-": "-", "×": "*", "÷": "/"}


def _init_state(key: str) -> None:
    if key not in st.session_state:
        st.session_state[key] = {"cols": [None], "ops": []}


def build_expression(df: pd.DataFrame, key_prefix: str = "") -> Tuple[str, bool]:
    """
    Renders a dynamic operand/operator builder inside a dialog.
    Returns (expression_string, valid_flag).
    """

    parts_key = f"{key_prefix}_expr_parts"
    _init_state(parts_key)
    state = st.session_state[parts_key]
    cols = state["cols"]
    ops = state["ops"]

    st.markdown("#### Build your formula")

    # --- First operand row ---
    c_op, c_btn, c_dummy = st.columns([4, 1, 1])
    operand = c_op.selectbox(
        "Operand 1",
        options=[""] + list(df.columns),
        index=([""] + list(df.columns)).index(cols[0]) if cols[0] in df.columns else 0,
        key=f"{key_prefix}_col_0",
        label_visibility="collapsed",
    )
    if c_btn.button("+", key=f"{key_prefix}_add_op_0"):
        if operand:
            cols.append(None)
            ops.append(list(OPS.keys())[0])
            cols[0] = operand

    # --- Additional operand/operator rows ---
    for i in range(1, len(cols)):
        c_op, c_btn, c_paren = st.columns([3.5, 1, 1])
        # Operator
        op_choice = st.session_state[parts_key]["ops"][i - 1]
        selected_op = c_btn.selectbox(
            "",
            options=list(OPS.keys()),
            index=list(OPS.keys()).index(op_choice) if op_choice in OPS else 0,
            key=f"{key_prefix}_op_{i-1}",
            label_visibility="collapsed",
        )
        ops[i - 1] = selected_op

        # Operand
        operand = c_op.selectbox(
            f"Operand {i+1}",
            options=[""] + list(df.columns),
            index=([""] + list(df.columns)).index(cols[i]) if cols[i] in df.columns else 0,
            key=f"{key_prefix}_col_{i}",
            label_visibility="collapsed",
        )
        cols[i] = operand or None

        # Add more operands?
        if c_paren.button("+", key=f"{key_prefix}_add_op_{i}"):
            cols.append(None)
            ops.append(list(OPS.keys())[0])

    # --- Parentheses row ---
    p1, p2, _ = st.columns([1, 1, 8])
    if p1.button("(", key=f"{key_prefix}_open_paren"):
        state["cols"].append("(")
    if p2.button(")", key=f"{key_prefix}_close_paren"):
        state["cols"].append(")")

    # --- Build expression string ---
    expr = ""
    valid = False
    # All operands must be non-None strings to build
    if all(isinstance(c, str) for c in cols if c is not None):
        # Construct expression: df['A'] OP df['B'] OP df['C'] ...
        tokens: List[str] = []
        for idx, col in enumerate(cols):
            if idx > 0:
                op = OPS.get(ops[idx - 1], None)
                if op:
                    tokens.append(op)
            if col in df.columns:
                tokens.append(f"df['{col}']")
            else:
                tokens.append(col)  # parentheses or stray token

        expr = " ".join(tokens)

        # Live preview
        try:
            preview = pd.DataFrame({"Result": eval(expr, {"df": df})}).head()
            st.dataframe(preview, use_container_width=True)
            valid = True
        except Exception as e:
            st.error(f"❌ Expression error: {e}")

    else:
        st.info("Select all operands to preview.")

    return expr, valid
