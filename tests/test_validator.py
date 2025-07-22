from schemas.template_v2 import Template, ValidationError
import json
from pathlib import Path


def load_sample(name: str) -> dict:
    txt = Path("templates") / f"{name}.json"
    return json.loads(txt.read_text())


def test_coa_template_valid():
    Template.parse_obj(load_sample("coa-template"))


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
    Template.parse_obj(pit)


def test_missing_layers_fails():
    bad = {"template_name": "oops", "layers": []}
    try:
        Template.parse_obj(bad)
    except ValidationError:
        return
    assert False, "Validation should fail when no layers"
