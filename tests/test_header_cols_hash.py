import sys
import types
import pandas as pd
import pytest

from schemas.template_v2 import FieldSpec, HeaderLayer
from pages.steps import header as header_step
from app_utils.ui import header_utils


class DummyStreamlit:
    def __init__(self) -> None:
        self.session_state: dict = {}

    class Spinner:
        def __enter__(self) -> "DummyStreamlit.Spinner":
            return self

        def __exit__(self, *exc: object) -> None:  # noqa: D401
            return None

    def header(self, *a: object, **k: object) -> None:
        pass

    subheader = success = error = info = header

    def warning(self, *a: object, **k: object) -> None:
        pass

    def spinner(self, *a: object, **k: object) -> "DummyStreamlit.Spinner":
        return self.Spinner()

    def rerun(self) -> None:  # noqa: D401
        return None

    def columns(self, spec: list[int] | int):
        if isinstance(spec, int):
            spec = range(spec)
        dummy = types.SimpleNamespace(
            selectbox=lambda *a, **k: "",
            button=lambda *a, **k: False,
            markdown=lambda *a, **k: None,
        )
        return [dummy for _ in spec]

    def caption(self, *a: object, **k: object) -> None:
        raise RuntimeError("stop")

    def selectbox(self, label: str, options: list[str], index: int = 0, **k: object):
        return options[index]

    def cache_data(self, *a: object, **k: object):
        def wrap(func):
            return func

        return wrap


def patch_streamlit(monkeypatch: pytest.MonkeyPatch) -> DummyStreamlit:
    st = DummyStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", st)
    monkeypatch.setattr(header_step, "st", st)
    monkeypatch.setattr(header_utils, "st", st)
    return st


def test_new_upload_triggers_remap(monkeypatch: pytest.MonkeyPatch) -> None:
    st = patch_streamlit(monkeypatch)

    def fake_read(file, sheet_name=None):
        if file == "file1":
            return pd.DataFrame({"A": [1]}), ["A"]
        return pd.DataFrame({"B": [1]}), ["B"]

    monkeypatch.setattr(header_step, "read_tabular_file", fake_read)

    call_count = {"n": 0}

    def fake_suggest(fields, cols):
        call_count["n"] += 1
        return {f: {"cols": tuple(cols), "call": call_count["n"]} for f in fields}

    monkeypatch.setattr(header_step, "suggest_header_mapping", fake_suggest)
    gpt_calls = {"n": 0}

    def fake_gpt(mapping, cols, targets=None):
        gpt_calls["n"] += 1
        return mapping

    monkeypatch.setattr(header_step, "apply_gpt_header_fallback", fake_gpt)

    st.session_state.update(
        {
            "uploaded_file": "file1",
            "upload_sheet": "Sheet1",
            "upload_sheets": ["Sheet1"],
            "current_template": "demo",
        }
    )

    layer = HeaderLayer(type="header", fields=[FieldSpec(key="Field")])
    with pytest.raises(RuntimeError):
        header_step.render(layer, 0)

    assert st.session_state["header_mapping_0"]["Field"]["cols"] == ("A",)
    st.session_state["header_ai_done_0"] = True

    st.session_state["uploaded_file"] = "file2"
    with pytest.raises(RuntimeError):
        header_step.render(layer, 0)

    assert st.session_state["header_mapping_0"]["Field"]["cols"] == ("B",)
    assert gpt_calls["n"] == 2


def test_missing_hash_triggers_remap(monkeypatch: pytest.MonkeyPatch) -> None:
    st = patch_streamlit(monkeypatch)

    monkeypatch.setattr(
        header_step, "read_tabular_file", lambda f, sheet_name=None: (pd.DataFrame({"A": [1]}), ["A"])
    )

    call_count = {"n": 0}

    def fake_suggest(fields, cols):
        call_count["n"] += 1
        return {f: {"call": call_count["n"]} for f in fields}

    monkeypatch.setattr(header_step, "suggest_header_mapping", fake_suggest)
    gpt_calls = {"n": 0}

    def fake_gpt(mapping, cols, targets=None):
        gpt_calls["n"] += 1
        return mapping

    monkeypatch.setattr(header_step, "apply_gpt_header_fallback", fake_gpt)

    st.session_state.update(
        {
            "uploaded_file": object(),
            "upload_sheet": "Sheet1",
            "upload_sheets": ["Sheet1"],
            "current_template": "demo",
        }
    )

    layer = HeaderLayer(type="header", fields=[FieldSpec(key="Field")])
    with pytest.raises(RuntimeError):
        header_step.render(layer, 0)

    assert call_count["n"] == 1
    st.session_state["header_ai_done_0"] = True
    st.session_state.pop("header_cols_0")

    with pytest.raises(RuntimeError):
        header_step.render(layer, 0)

    assert call_count["n"] == 2
    assert gpt_calls["n"] == 2

