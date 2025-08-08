import json
from pathlib import Path

from schemas.template_v2 import Template
from app_utils.mapping.exporter import build_output_template


def load_sample(name: str) -> Template:
    txt = Path("templates") / f"{name}.json"
    tpl = Template.model_validate(json.loads(txt.read_text()))
    assert tpl.template_guid
    return tpl


def test_expressions_in_output():
    template = load_sample("standard-fm-coa")
    state = {
        "header_mapping_0": {
            "NET_CHANGE": {"expr": "df['A'] + df['B']"}
        },
        "computed_result_2": {
            "resolved": True,
            "method": "derived",
            "source_cols": ["A", "B"],
            "expression": "df['A'] - df['B']"
        }
    }
    out = build_output_template(template, state, process_guid="guid1")
    header_layer = out["layers"][0]
    net_change = next(f for f in header_layer["fields"] if f["key"] == "NET_CHANGE")
    assert net_change["expression"] == "df['A'] + df['B']"

    computed_layer = out["layers"][2]
    formula = computed_layer["formula"]
    assert formula["strategy"] == "first_available"
    derived = [c for c in formula["candidates"] if c["type"] == "derived"]
    assert any(c["expression"] == "$A - $B" for c in derived)


def test_extra_fields_preserved():
    template = load_sample("standard-fm-coa")
    state = {
        "header_mapping_0": {"NEW_COL": {"src": "A"}},
        "header_extra_fields_0": ["NEW_COL"],
    }
    out = build_output_template(template, state, process_guid="guid2")
    header_layer = out["layers"][0]
    added = next(f for f in header_layer["fields"] if f["key"] == "NEW_COL")
    assert added["source"] == "A"


def test_extra_field_expression():
    template = load_sample("standard-fm-coa")
    state = {
        "header_mapping_0": {"ADDED": {"expr": "df['A']*2"}},
        "header_extra_fields_0": ["ADDED"],
    }
    out = build_output_template(template, state, process_guid="guid3")
    header_layer = out["layers"][0]
    added = next(f for f in header_layer["fields"] if f["key"] == "ADDED")
    assert added["expression"] == "df['A']*2"


def test_process_guid_added():
    template = load_sample("standard-fm-coa")
    state = {}
    out = build_output_template(template, state, process_guid="123")
    assert out.get("process_guid") == "123"


def test_lookup_mapping_saved():
    template = load_sample("standard-fm-coa")
    state = {"lookup_mapping_1": {"STD": "Client"}}
    out = build_output_template(template, state, process_guid="guid4")
    lookup_layer = out["layers"][1]
    assert lookup_layer["mapping"]["STD"] == "Client"
