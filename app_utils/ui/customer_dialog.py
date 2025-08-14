from __future__ import annotations
"""Modal dialog for creating a new customer."""

import streamlit as st

from app_utils.azure_sql import fetch_customers, insert_customer


def open_new_customer_dialog(client_scac: str, operational_scac: str) -> None:
    """Open modal to add a customer and refresh list on save."""

    @st.dialog("Add Customer", width="small")
    def _dialog() -> None:
        name = st.text_input("Customer Name")
        billto_id = st.text_input("Customer ID")
        if st.button("💾 Save", disabled=not name.strip()):
            try:
                insert_customer(client_scac, name.strip(), billto_id.strip() or None)
            except Exception as err:  # pragma: no cover - UI feedback only
                st.error(f"Failed to add customer: {err}")
                return
            customers = fetch_customers(operational_scac)
            st.session_state["customer_options"] = customers
            if customers:
                st.session_state["client_scac"] = customers[0]["CLIENT_SCAC"]
            st.session_state["customer_name"] = name.strip().title()
            st.session_state["customer_ids"] = (
                [billto_id.strip()] if billto_id.strip() else []
            )
            st.rerun()

    _dialog()
