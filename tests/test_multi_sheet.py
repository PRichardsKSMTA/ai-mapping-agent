import sys
import types
import pandas as pd
import pytest

from schemas.template_v2 import (
    FieldSpec,
    HeaderLayer,
    ComputedLayer,
    ComputedFormula,
    LookupLayer,
)
from pages.steps import header as header_step
from pages.steps import computed as computed_step
from pages.steps import lookup as lookup_step


class DummyStreamlit:
    def __init__(self):
        self.session_state = {}

    class Spinner:
        def __enter__(self):
            return self

        def __exit__(self, *exc) -> None:
            pass

    def header(self, *a, **k):
        pass

    def error(self, msg):
        raise RuntimeError(msg)

    def spinner(self, *a, **k):
        return self.Spinner()


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

    layer = ComputedLayer(
        type="computed", sheet="Second", target_field="X", formula=ComputedFormula()
    )
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


class DummyContainer:
    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        pass

    def markdown(self, *a, **k) -> None:
        pass

    def progress(self, *a, **k) -> None:
        pass


class WizardSidebar:
    def __enter__(self) -> "WizardSidebar":
        return self

    def __exit__(self, *exc) -> None:
        pass

    def subheader(self, *a, **k) -> None:
        pass

    def selectbox(self, label, options, index=0, **k):
        return options[index]

    def empty(self) -> DummyContainer:
        return DummyContainer()

    def write(self, *a, **k) -> None:
        pass

    def info(self, *a, **k) -> None:
        pass


class WizardStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, object] = {}
        self.sidebar = WizardSidebar()

    def set_page_config(self, *a, **k) -> None:
        pass

    def title(self, *a, **k) -> None:
        pass

    header = subheader = success = error = write = warning = info = title

    def selectbox(self, label, options, index=0, **k):
        return options[index]

    def file_uploader(self, *a, **k):
        return None

    def button(self, *a, **k):
        return False

    def spinner(self, *a, **k):
        return DummyContainer()

    def empty(self) -> DummyContainer:
        return DummyContainer()

    def rerun(self) -> None:
        raise RuntimeError("stop")

    def stop(self) -> None:
        raise RuntimeError("stop")

    def markdown(self, *a, **k) -> None:
        pass

    caption = markdown

    def columns(self, spec):
        if isinstance(spec, int):
            spec = range(spec)
        dummy = types.SimpleNamespace(
            selectbox=lambda *a, **k: "",
            button=lambda *a, **k: False,
            markdown=lambda *a, **k: None,
        )
        return [dummy for _ in spec]

    def cache_data(self, *a, **k):
        def wrap(func):
            return func

        return wrap


def test_multiple_computed_layers_need_confirmation(monkeypatch):
    st = WizardStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", st)
    monkeypatch.setattr(header_step, "st", st)
    monkeypatch.setattr(computed_step, "st", st)
    st.button = lambda label, *a, **k: label == "Confirm Header Mapping"
    monkeypatch.setattr(
        header_step,
        "read_tabular_file",
        lambda *_a, **_k: (pd.DataFrame({"A": [1]}), ["A"]),
    )

    st.session_state.update(
        {
            "uploaded_file": object(),
            "upload_sheet": 0,
            "current_template": "demo",
            "header_ai_done_0": True,
        }
    )
    header_layer = HeaderLayer(type="header", fields=[FieldSpec(key="A")])
    with pytest.raises(RuntimeError):
        header_step.render(header_layer, 0)

    assert "auto_computed_confirm" not in st.session_state
    assert st.session_state["layer_confirmed_0"] is True
