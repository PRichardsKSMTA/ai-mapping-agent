import sys
import pandas as pd
import pytest

from schemas.template_v2 import ComputedLayer, ComputedFormula
from pages.steps import computed as computed_step


class DummyStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, object] = {}

    class Spinner:
        def __enter__(self):
            return self

        def __exit__(self, *exc) -> None:
            pass

    def header(self, *a, **k):
        pass

    success = info = warning = error = header

    def spinner(self, *a, **k):
        return self.Spinner()

    def radio(self, label, options, key=None):  # noqa: D401 - doc string not needed
        return options[0]

    def selectbox(self, label, options, index=0, key=None, **k):
        return options[index]

    def markdown(self, *a, **k):
        pass

    def button(self, *a, **k):
        return False


from _pytest.monkeypatch import MonkeyPatch


def patch_streamlit(monkeypatch: MonkeyPatch) -> DummyStreamlit:
    st = DummyStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", st)
    monkeypatch.setattr(computed_step, "st", st)
    return st


def test_render_with_pydantic_layer(monkeypatch: MonkeyPatch) -> None:
    st = patch_streamlit(monkeypatch)

    monkeypatch.setattr(
        computed_step,
        "read_tabular_file",
        lambda *_a, **_k: (pd.DataFrame({"A": [1]}), ["A"]),
    )

    st.session_state.update({"uploaded_file": object(), "upload_sheet": 0})

    layer = ComputedLayer(type="computed", target_field="X", formula=ComputedFormula())
    computed_step.render(layer, 0)

    assert "computed_result_0" in st.session_state

