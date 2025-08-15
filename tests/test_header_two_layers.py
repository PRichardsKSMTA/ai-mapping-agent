import sys
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

        def __exit__(self, *exc) -> None:
            pass

    def header(self, *a, **k):
        pass

    def error(self, msg):
        raise RuntimeError(msg)

    def spinner(self, *a, **k):
        return self.Spinner()

    def rerun(self):
        pass


def patch_streamlit(monkeypatch):
    st = DummyStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", st)
    monkeypatch.setattr(header_step, "st", st)
    monkeypatch.setattr(
        header_step, "suggest_header_mapping", lambda fields, cols: {k: {} for k in fields}
    )
    return st


def test_two_header_layers(monkeypatch):
    st = patch_streamlit(monkeypatch)

    def fake_read(_file, sheet_name=None):
        return pd.DataFrame({"A": [1]}), ["A"]

    monkeypatch.setattr(header_step, "read_tabular_file", fake_read)
    monkeypatch.setattr(
        header_step, "apply_gpt_header_fallback", lambda m, c, targets=None: m
    )
    st.caption = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stop"))

    st.session_state.update({
        "uploaded_file": object(),
        "upload_sheet": "First",
        "current_template": "demo",
    })

    layers = [
        HeaderLayer(type="header", sheet="First", fields=[FieldSpec(key="A")]),
        HeaderLayer(type="header", sheet="First", fields=[FieldSpec(key="A")]),
    ]

    for idx, layer in enumerate(layers):
        with pytest.raises(RuntimeError):
            header_step.render(layer, idx)

    assert st.session_state["header_mapping_0"]["A"] == {}
    assert st.session_state["header_mapping_1"]["A"] == {}
