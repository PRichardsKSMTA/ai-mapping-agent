import json
from pathlib import Path
import pytest
from schemas.template_v2 import Template, ValidationError


def load_sample(name: str) -> dict:
    txt = Path("templates") / f"{name}.json"
    return json.loads(txt.read_text())


def test_coa_template_valid():
    Template.model_validate(load_sample("standard-fm-coa"))


def test_pit_header_only_valid():
    pit = {
        "template_name": "pit-bid",
        "layers": [
            {
                "type": "header",
                "fields": [{"key": "Lane ID"}, {"key": "Orig Zip"}],
            }
        ],
    }
    Template.model_validate(pit)


def test_postprocess_valid():
    tpl = {
        "template_name": "demo",
        "layers": [
            {"type": "header", "fields": [{"key": "A"}]}
        ],
        "postprocess": {
            "type": "sql_insert",
            "connection": "mssql://example",
            "table": "dbo.OUT",
            "column_map": {"A": "A"},
        },
    }
    Template.model_validate(tpl)


def test_postprocess_missing_type_fails():
    tpl = {
        "template_name": "demo",
        "layers": [{"type": "header", "fields": [{"key": "A"}]}],
        "postprocess": {"table": "dbo.OUT"},
    }
    with pytest.raises(ValidationError):
        Template.model_validate(tpl)


def test_missing_layers_fails():
    bad = {"template_name": "oops", "layers": []}
    try:
        Template.model_validate(bad)
    except ValidationError:
        return
    assert False, "Validation should fail when no layers"
