import importlib
import sys
from typing import Any, List

import pandas as pd
import pytest


class DummyColumn:
    def __init__(self, pressed: bool = False) -> None:
        self.pressed = pressed

    def button(self, *a: Any, **k: Any) -> bool:  # pragma: no cover - trivial
        if self.pressed and (func := k.get("on_click")):
            func(*k.get("args", ()))
        return self.pressed


class DummyStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, Any] = {}
        self.last_dataframe: pd.DataFrame | None = None

    def dialog(self, *a: Any, **k: Any):  # pragma: no cover - trivial
        def wrap(func: Any) -> Any:
            return func

        return wrap

    def markdown(self, *a: Any, **k: Any) -> None:  # pragma: no cover - trivial
        pass

    def text_area(self, label: str, *, key: str, **k: Any) -> str:  # pragma: no cover
        self.session_state.setdefault(key, "")
        return self.session_state[key]

    def info(self, *a: Any, **k: Any) -> None:  # pragma: no cover - trivial
        pass

    def error(self, *a: Any, **k: Any) -> None:  # pragma: no cover - trivial
        pass

    def dataframe(self, data: Any, *a: Any, **k: Any) -> None:  # pragma: no cover
        if isinstance(data, pd.DataFrame):
            self.last_dataframe = data
        else:
            self.last_dataframe = pd.DataFrame(data)

    def rerun(self) -> None:  # pragma: no cover - trivial
        pass

    def columns(self, spec: Any) -> List[DummyColumn]:
        if isinstance(spec, int):
            return [DummyColumn(False), DummyColumn(True)]
        return [DummyColumn(False) for _ in spec]


def run_dialog(
    monkeypatch: Any,
    key: str,
    df: pd.DataFrame | None = None,
    expr: str = "df['A']",
) -> tuple[list[Any], DummyStreamlit]:
    df = df if df is not None else pd.DataFrame({"A": [1, 2]})
    dummy = DummyStreamlit()
    dummy.session_state["current_template"] = "Demo"
    dummy.session_state[f"{key}_expr_text"] = expr
    monkeypatch.setitem(sys.modules, "streamlit", dummy)
    sys.modules.pop("app_utils.ui.formula_dialog", None)
    mod = importlib.import_module("app_utils.ui.formula_dialog")
    calls: list[Any] = []
    monkeypatch.setattr(mod, "add_suggestion", lambda *a, **k: calls.append(1))
    mod.open_formula_dialog(df, key)
    return calls, dummy


def test_persist_for_standard_field(monkeypatch) -> None:
    calls, _ = run_dialog(monkeypatch, "Total")
    assert calls


def test_skip_persist_for_adhoc(monkeypatch) -> None:
    calls, _ = run_dialog(monkeypatch, "ADHOC_INFO1")
    assert not calls


def test_preview_coerces_numeric_strings(monkeypatch) -> None:
    df = pd.DataFrame({"A": ["12", "3.14"], "B": ["3", "0.5"]})
    _, dummy = run_dialog(monkeypatch, "Total", df=df, expr="df['A'] / df['B']")
    assert dummy.last_dataframe is not None
    results = dummy.last_dataframe["Result"].tolist()
    assert results == pytest.approx([4.0, 6.28])
    assert dummy.last_dataframe["Result"].dtype.kind in {"f", "i"}
