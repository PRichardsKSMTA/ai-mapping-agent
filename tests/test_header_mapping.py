import pytest

from app_utils.mapping_utils import suggest_header_mapping
from pages.steps.header import remove_field
import streamlit as st


def test_header_mapping_confidence():
    fields = ["Balance", "Amount"]
    cols = ["balance", "amount"]
    res = suggest_header_mapping(fields, cols)
    assert res["Balance"]["src"] == "balance"
    assert res["Balance"]["confidence"] == 1.0
    assert res["Amount"]["src"] == "amount"
    assert res["Amount"]["confidence"] == 1.0


def test_header_mapping_no_match():
    res = suggest_header_mapping(["Date"], ["amount"])
    assert res["Date"] == {}


def test_remove_field_updates_state():
    idx = 0
    map_key = f"header_mapping_{idx}"
    extra_key = f"header_extra_fields_{idx}"

    st.session_state.clear()
    st.session_state[map_key] = {"Extra": {}, "Name": {}}
    st.session_state[extra_key] = ["Extra"]

    remove_field("Extra", idx)

    assert "Extra" not in st.session_state[map_key]
    assert "Extra" not in st.session_state[extra_key]


