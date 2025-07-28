import sys
import types
import pandas as pd
import pytest

from schemas.template_v2 import FieldSpec, HeaderLayer, ComputedLayer, ComputedFormula, LookupLayer, Template
from pages.steps import header as header_step
from pages.steps import computed as computed_step
from pages.steps import lookup as lookup_step


class DummyStreamlit:
    def __init__(self):
        self.session_state = {}

    def header(self, *a, **k):
        pass

    def error(self, msg):
        raise RuntimeError(msg)


def patch_streamlit(monkeypatch):
    st = DummyStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", st)
    monkeypatch.setattr(header_step, "st", st)
    monkeypatch.setattr(computed_step, "st", st)
    monkeypatch.setattr(lookup_step, "st", st)
    return st


def test_header_uses_layer_sheet(monkeypatch):
    st = patch_streamlit(monkeypatch)

    captured = {}

    def fake_read(_file, sheet_name=0):
        captured["sheet"] = sheet_name
        raise RuntimeError("stop")

    monkeypatch.setattr(header_step, "read_tabular_file", fake_read)

    st.session_state["uploaded_file"] = object()
    st.session_state["upload_sheet"] = "First"

    layer = HeaderLayer(type="header", sheet="Second", fields=[FieldSpec(key="B")])
    with pytest.raises(RuntimeError):
        header_step.render(layer, 0)

    assert captured["sheet"] == "Second"


def test_computed_uses_layer_sheet(monkeypatch):
    st = patch_streamlit(monkeypatch)

    captured = {}

    def fake_read(_file, sheet_name=0):
        captured["sheet"] = sheet_name
        raise RuntimeError("stop")

    monkeypatch.setattr(computed_step, "read_tabular_file", fake_read)

    st.session_state["uploaded_file"] = object()
    st.session_state["upload_sheet"] = "First"

    layer = ComputedLayer(type="computed", sheet="Second", target_field="X", formula=ComputedFormula())
    with pytest.raises(RuntimeError):
        computed_step.render(layer, 0)

    assert captured["sheet"] == "Second"


def test_lookup_dictionary_sheet(monkeypatch):
    st = patch_streamlit(monkeypatch)

    def fake_read(_file, sheet_name=None):
        return pd.DataFrame({"A": [1]}), ["A"]

    monkeypatch.setattr(lookup_step, "read_tabular_file", fake_read)

    captured = {}

    def fake_match(src_vals, dict_vals):
        captured["dict"] = dict_vals
        raise RuntimeError("stop")

    monkeypatch.setattr(lookup_step, "match_lookup_values", fake_match)

    st.session_state["uploaded_file"] = object()
    st.session_state["upload_sheet"] = "First"

    layer = LookupLayer(
        type="lookup",
        sheet="First",
        source_field="A",
        target_field="A",
        dictionary_sheet="dictsheet",
    )

    template_dict = {
        "template_name": "demo",
        "layers": [layer.model_dump()],
        "dictsheet": [{"A": "one"}, {"A": "two"}],
    }
    st.session_state["template"] = template_dict

    with pytest.raises(RuntimeError):
        lookup_step.render(layer, 0)

    assert captured["dict"] == ["one", "two"]

