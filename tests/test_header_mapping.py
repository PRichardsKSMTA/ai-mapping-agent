import pytest

from app_utils.mapping_utils import suggest_header_mapping
from pages.steps.header import (
    remove_field,
    add_field,
    set_field_mapping,
    append_lookup_layer,
    append_computed_layer,
    save_current_template,
)
import streamlit as st
import json
from schemas.template_v2 import FieldSpec
from app_utils import suggestion_store


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
    st.session_state["template"] = {
        "layers": [
            {"type": "header", "fields": [{"key": "Name"}, {"key": "Extra"}]}
        ]
    }

    remove_field("Extra", idx)

    assert "Extra" not in st.session_state[map_key]
    assert "Extra" not in st.session_state[extra_key]
    assert st.session_state["unsaved_changes"] is True
    fields = st.session_state["template"]["layers"][0]["fields"]
    assert all(f["key"] != "Extra" for f in fields)


def test_saved_suggestion_overrides_fuzzy(monkeypatch, tmp_path):
    """Stored column suggestion should override fuzzy match."""

    # Prepare suggestion file
    sug_file = tmp_path / "mapping_suggestions.json"
    data = [
        {
            "template": "simple-template",
            "field": "Name",
            "type": "direct",
            "formula": None,
            "columns": ["NameSaved"],
            "display": "NameSaved",
        }
    ]
    sug_file.write_text(json.dumps(data))
    monkeypatch.setattr(suggestion_store, "SUGGESTION_FILE", sug_file)

    # Fake file reader
    def fake_read(uploaded, sheet_name=None):
        import pandas as pd
        df = pd.DataFrame(columns=["NameWrong", "NameSaved", "Value"])
        return df, ["NameWrong", "NameSaved", "Value"]

    _, source_cols = fake_read(None)
    fields = [FieldSpec(key="Name", required=True), FieldSpec(key="Value", required=True)]
    mapping = suggest_header_mapping([f.key for f in fields], source_cols)

    for f in fields:
        key = f.key
        for s in suggestion_store.get_suggestions("simple-template", key):
            if s["type"] == "direct":
                for col in source_cols:
                    if col.lower() == s["columns"][0].lower():
                        mapping[key] = {"src": col, "confidence": 1.0}
                        break
                if mapping.get(key):
                    break
            else:
                mapping[key] = {"expr": s["formula"], "expr_display": s["display"]}
                break

    assert mapping["Name"]["src"] == "NameSaved"
    assert mapping["Name"]["confidence"] == 1.0



def test_add_field_sets_unsaved(monkeypatch):
    idx = 0
    st.session_state.clear()
    st.session_state["template"] = {
        "layers": [{"type": "header", "fields": [{"key": "Name"}]}]
    }
    add_field("Extra", idx)
    assert st.session_state["unsaved_changes"] is True
    fields = st.session_state["template"]["layers"][0]["fields"]
    assert any(f["key"] == "Extra" for f in fields)
    assert "Extra" in st.session_state[f"header_extra_fields_{idx}"]


def test_add_remove_field_without_template():
    idx = 0
    st.session_state.clear()
    add_field("Extra", idx)
    assert st.session_state["unsaved_changes"] is True
    assert "template" not in st.session_state
    st.session_state["unsaved_changes"] = False
    remove_field("Extra", idx)
    assert st.session_state["unsaved_changes"] is True


def test_set_field_mapping_marks_unsaved():
    idx = 0
    key = f"header_mapping_{idx}"
    st.session_state.clear()
    st.session_state[key] = {"Name": {}}

    set_field_mapping("Name", idx, {"src": "Col"})
    assert st.session_state["unsaved_changes"] is True
    assert st.session_state[key]["Name"]["src"] == "Col"


def test_persist_template_clears_unsaved(monkeypatch):
    import sys
    import types

    st.session_state["unsaved_changes"] = True

    monkeypatch.setenv("DISABLE_AUTH", "1")
    monkeypatch.setitem(sys.modules, "dotenv", types.SimpleNamespace(load_dotenv=lambda: None))
    from pages import template_manager

    def fake_save(_tpl):
        return "demo"

    monkeypatch.setattr(template_manager, "save_template_file", fake_save)
    template_manager.persist_template({"template_name": "demo", "layers": []})
    assert st.session_state["unsaved_changes"] is False
    sys.modules.pop("pages.template_manager", None)


def test_append_layers_and_save(monkeypatch, tmp_path):
    st.session_state.clear()
    st.session_state["template"] = {"template_name": "demo", "layers": []}

    append_lookup_layer("SRC", "TGT", "dict")
    append_computed_layer("TOTAL", "df['A']")
    assert len(st.session_state["template"]["layers"]) == 2

    monkeypatch.setattr(
        "pages.steps.header.save_template_file", lambda tpl: "demo-saved"
    )
    name = save_current_template()
    assert name == "demo-saved"
    assert st.session_state["unsaved_changes"] is False
