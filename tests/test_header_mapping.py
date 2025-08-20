import pytest
import types
from pathlib import Path

from app_utils.mapping_utils import suggest_header_mapping
from app_utils.ui.header_utils import (
    remove_field,
    add_field,
    set_field_mapping,
    persist_suggestions_from_mapping,
    remove_formula,
)
import streamlit as st
import json
from schemas.template_v2 import FieldSpec
from app_utils import suggestion_store
from app_utils.mapping import header_layer


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


def test_adhoc_and_optional_unmapped():
    cols = ["ID"]
    fields = ["Temp Cat", "ADHOC_INFO1"]
    res = suggest_header_mapping(fields, cols)
    assert res["Temp Cat"] == {}
    assert res["ADHOC_INFO1"] == {}


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
        for s in suggestion_store.get_suggestions("simple-template", key, headers=source_cols):
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


def test_set_field_mapping_does_not_mark_unsaved():
    idx = 0
    key = f"header_mapping_{idx}"
    st.session_state.clear()
    st.session_state[key] = {"Name": {}}

    set_field_mapping("Name", idx, {"src": "Col"})
    assert "unsaved_changes" not in st.session_state
    assert st.session_state[key]["Name"]["src"] == "Col"


def test_persist_template_clears_unsaved(monkeypatch):
    import sys
    import types

    st.session_state["unsaved_changes"] = True

    monkeypatch.setenv("DISABLE_AUTH", "1")
    monkeypatch.setitem(sys.modules, "dotenv", types.SimpleNamespace(load_dotenv=lambda: None))
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "pages.template_manager",
        Path(__file__).resolve().parents[1] / "pages/📝_Template_Manager.py",
    )
    template_manager = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(template_manager)

    def fake_save(_tpl):
        return "demo"

    monkeypatch.setattr(template_manager, "save_template_file", fake_save)
    template_manager.persist_template({"template_name": "demo", "layers": []})
    assert st.session_state["unsaved_changes"] is False
    sys.modules.pop("pages.template_manager", None)



def test_persist_suggestions_from_mapping(monkeypatch, tmp_path):
    st.session_state.clear()
    sug_file = tmp_path / "mapping_suggestions.json"
    monkeypatch.setattr(suggestion_store, "SUGGESTION_FILE", sug_file)

    st.session_state["current_template"] = "demo"
    layer = types.SimpleNamespace(fields=[FieldSpec(key="Name"), FieldSpec(key="Calc")])
    mapping = {
        "Name": {"src": "ColA"},
        "Calc": {"expr": "df['A'] + df['B']", "expr_display": "A + B"},
    }

    persist_suggestions_from_mapping(layer, mapping, ["ColA", "A", "B"])

    saved = json.loads(sug_file.read_text())
    assert saved[0]["columns"] == ["ColA"]
    assert saved[1]["formula"] == "df['A'] + df['B']"


def _prepare_suggestion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[int, str, list[dict], Path]:
    idx = 0
    map_key = f"header_mapping_{idx}"
    st.session_state.clear()
    st.session_state[map_key] = {"Calc": {"expr": "df['A']", "expr_display": "A"}}
    st.session_state["current_template"] = "demo"
    sug_file = tmp_path / "mapping_suggestions.json"
    data: list[dict] = [
        {
            "template": "demo",
            "field": "Calc",
            "type": "formula",
            "formula": "df['A']",
            "columns": ["A"],
            "display": "A",
        }
    ]
    sug_file.write_text(json.dumps(data))
    monkeypatch.setattr(suggestion_store, "SUGGESTION_FILE", sug_file)
    return idx, map_key, data, sug_file


def test_remove_formula_keeps_suggestion(monkeypatch, tmp_path):
    idx, map_key, data, sug_file = _prepare_suggestion(monkeypatch, tmp_path)
    remove_formula("Calc", idx)
    assert st.session_state[map_key]["Calc"] == {}
    assert json.loads(sug_file.read_text()) == data


def test_remove_formula_forget_suggestion(monkeypatch, tmp_path):
    idx, map_key, _, sug_file = _prepare_suggestion(monkeypatch, tmp_path)
    remove_formula("Calc", idx, drop_suggestion=True)
    assert st.session_state[map_key]["Calc"] == {}
    assert json.loads(sug_file.read_text()) == []


def test_exact_match_prepopulates_optional(monkeypatch):
    """Exact column names should remain mapped after GPT fallback."""

    monkeypatch.setattr(
        header_layer, "apply_gpt_header_fallback", lambda m, *_a, **_k: m
    )

    fields = [
        FieldSpec(key="Lane ID", required=True),
        FieldSpec(key="Origin City", required=False),
    ]
    cols = ["Lane ID", "Origin City"]

    mapping = suggest_header_mapping([f.key for f in fields], cols)
    mapping = header_layer.apply_gpt_header_fallback(mapping, cols, targets=["Lane ID"])

    assert mapping["Lane ID"]["src"] == "Lane ID"
    assert mapping["Origin City"]["src"] == "Origin City"


def test_saved_suggestion_prepopulates(monkeypatch, tmp_path):
    """Stored suggestions should map optional fields."""

    monkeypatch.setattr(
        header_layer, "apply_gpt_header_fallback", lambda m, *_a, **_k: m
    )

    sug_file = tmp_path / "mapping_suggestions.json"
    data = [
        {
            "template": "PIT BID",
            "field": "Origin City",
            "type": "direct",
            "formula": None,
            "columns": ["OC"],
            "display": "OC",
        }
    ]
    sug_file.write_text(json.dumps(data))
    monkeypatch.setattr(suggestion_store, "SUGGESTION_FILE", sug_file)

    fields = [
        FieldSpec(key="Lane ID", required=True),
        FieldSpec(key="Origin City", required=False),
    ]
    cols = ["Lane ID", "OC"]

    mapping = suggest_header_mapping([f.key for f in fields], cols)
    for field in fields:
        key = field.key
        for s in suggestion_store.get_suggestions("PIT BID", key, headers=cols):
            if s["type"] == "direct":
                for col in cols:
                    if col.lower() == s["columns"][0].lower():
                        mapping[key] = {"src": col, "confidence": 1.0}
                        break
                if mapping.get(key):
                    break

    mapping = header_layer.apply_gpt_header_fallback(mapping, cols, targets=["Lane ID"])

    assert mapping["Origin City"]["src"] == "OC"
