from __future__ import annotations
"""Modal dialog for creating a new customer."""

import streamlit as st


def open_new_customer_dialog(client_scac: str, operational_scac: str) -> None:
    """Open modal to add a customer; saving is disabled."""

    @st.dialog("Add Customer", width="small")
    def _dialog() -> None:
        name = st.text_input("Customer Name")
        billto_id = st.text_input("Customer ID")
        if st.button("💾 Save", disabled=not name.strip()):
            st.error("Customer creation is disabled.")

    _dialog()
