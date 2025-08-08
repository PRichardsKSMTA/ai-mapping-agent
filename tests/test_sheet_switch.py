import sys
import types
import pandas as pd
import pytest

from schemas.template_v2 import FieldSpec, HeaderLayer
from pages.steps import header as header_step

class DummyStreamlit:
    def __init__(self):
        self.session_state = {}

    class Spinner:
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            pass

    def header(self, *a, **k):
        pass
    subheader = success = error = info = header

    def warning(self, *a, **k):
        pass

    def spinner(self, *a, **k):
        return self.Spinner()

    def rerun(self):
        pass

    def columns(self, spec):
        if isinstance(spec, int):
            spec = range(spec)
        dummy = types.SimpleNamespace(
            selectbox=lambda *a, **k: "",
            button=lambda *a, **k: False,
            markdown=lambda *a, **k: None,
        )
        return [dummy for _ in spec]

    def caption(self, *a, **k):
        raise RuntimeError("stop")

    def selectbox(self, label, options, index=0, **k):
        return options[index]

    def cache_data(self, *a, **k):
        def wrap(func):
            return func
        return wrap


def patch_streamlit(monkeypatch):
    st = DummyStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", st)
    monkeypatch.setattr(header_step, "st", st)
    return st


def test_auto_switch_sheet(monkeypatch):
    st = patch_streamlit(monkeypatch)

    def fake_read(_file, sheet_name=None):
        if sheet_name == "First":
            raise ValueError("bad")
        return pd.DataFrame({"B": [2]}), ["B"]

    monkeypatch.setattr(header_step, "read_tabular_file", fake_read)
    monkeypatch.setattr(
        header_step, "apply_gpt_header_fallback", lambda m, c, targets=None: m
    )

    st.session_state.update({
        "uploaded_file": object(),
        "upload_sheet": "First",
        "upload_sheets": ["First", "Second"],
        "current_template": "demo",
    })

    layer = HeaderLayer(type="header", fields=[FieldSpec(key="B")])
    with pytest.raises(RuntimeError):
        header_step.render(layer, 0)

    assert st.session_state["upload_sheet"] == "Second"
    assert st.session_state["header_mapping_0"]["B"] == {}


def test_sheet_change_recomputes_mapping(monkeypatch):
    st = patch_streamlit(monkeypatch)

    def fake_read(_file, sheet_name=None):
        if sheet_name == "First":
            return pd.DataFrame({"A": [1]}), ["A"]
        return pd.DataFrame({"B": [1]}), ["B"]

    monkeypatch.setattr(header_step, "read_tabular_file", fake_read)
    monkeypatch.setattr(
        header_step, "apply_gpt_header_fallback", lambda m, c, targets=None: m
    )

    st.session_state.update({
        "uploaded_file": object(),
        "upload_sheet": "First",
        "upload_sheets": ["First", "Second"],
        "current_template": "demo",
    })

    layer = HeaderLayer(type="header", fields=[FieldSpec(key="B")])
    with pytest.raises(RuntimeError):
        header_step.render(layer, 0)

    assert st.session_state["header_mapping_0"]["B"] == {}

    st.session_state["upload_sheet"] = "Second"
    with pytest.raises(RuntimeError):
        header_step.render(layer, 0)

    assert st.session_state["header_sheet_0"] == "Second"
    assert st.session_state["header_mapping_0"]["B"] == {}
