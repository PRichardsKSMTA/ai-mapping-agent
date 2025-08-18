import importlib
import json
import sys
import types
from pathlib import Path
from typing import Any


class DummyStreamlit:
    def __init__(
        self,
        *,
        pressed_labels: set[str] | None = None,
        pressed_keys: set[str] | None = None,
        session_state: dict | None = None,
    ) -> None:
        self.session_state = session_state or {}
        self.pressed_labels = pressed_labels or set()
        self.pressed_keys = pressed_keys or set()
        self.text_inputs: list[tuple[str, str]] = []

    # basic widgets -------------------------------------------------
    def dialog(self, *a, **k):
        def wrap(func):
            return func

        return wrap

    def text_input(self, label: str, value: str = "", key: str | None = None, **k):
        self.text_inputs.append((label, value))
        return self.session_state.get(key, value)

    def button(self, label: str, *, key: str | None = None, **k) -> bool:
        return label in self.pressed_labels or (key is not None and key in self.pressed_keys)

    def columns(self, spec):
        if isinstance(spec, int):
            spec = range(spec)
        return [
            types.SimpleNamespace(button=self.button, text_input=self.text_input)
            for _ in spec
        ]

    def subheader(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass

    def rerun(self) -> None:
        pass


def run_dialog(
    monkeypatch,
    tmp_path,
    *,
    suggestions: list[dict] | None = None,
    pressed_labels: set[str] | None = None,
    pressed_keys: set[str] | None = None,
    session_state: dict | None = None,
) -> tuple[DummyStreamlit, Any]:
    monkeypatch.chdir(tmp_path)
    tpl_dir = Path("templates")
    tpl_dir.mkdir()
    (tpl_dir / "demo.json").write_text(
        json.dumps(
            {"template_name": "Demo", "layers": [{"type": "header", "fields": [{"key": "Name"}]}]}
        )
    )
    sugg_file = Path("mapping_suggestions.json")
    sugg_file.write_text(json.dumps(suggestions or []))
    monkeypatch.setenv("SUGGESTION_FILE", str(sugg_file))
    from app_utils import suggestion_store

    importlib.reload(suggestion_store)

    dummy = DummyStreamlit(
        pressed_labels=pressed_labels,
        pressed_keys=pressed_keys,
        session_state=session_state,
    )
    monkeypatch.setitem(sys.modules, "streamlit", dummy)
    sys.modules.pop("app_utils.ui.suggestion_dialog", None)
    suggestion_dialog = importlib.import_module("app_utils.ui.suggestion_dialog")

    suggestion_dialog.edit_suggestions("demo.json", "Demo")
    sys.modules.pop("app_utils.ui.suggestion_dialog", None)
    return dummy, suggestion_store


def test_list_existing_suggestions(monkeypatch, tmp_path):
    dummy, _ = run_dialog(
        monkeypatch,
        tmp_path,
        suggestions=[
            {
                "template": "Demo",
                "field": "Name",
                "type": "direct",
                "columns": ["ColA"],
                "display": "ColA",
            }
        ],
    )
    assert any(val == "ColA" for _, val in dummy.text_inputs)


def test_add_suggestion(monkeypatch, tmp_path):
    session = {"new_cols_Name": "ColB", "new_disp_Name": "ColB"}
    _, store = run_dialog(
        monkeypatch,
        tmp_path,
        pressed_labels={"Add Name"},
        session_state=session,
    )
    res = store.get_suggestions("Demo", "Name")
    assert res and res[0]["columns"] == ["ColB"]


def test_delete_suggestion(monkeypatch, tmp_path):
    _, store = run_dialog(
        monkeypatch,
        tmp_path,
        suggestions=[
            {
                "template": "Demo",
                "field": "Name",
                "type": "direct",
                "columns": ["ColA"],
                "display": "ColA",
            }
        ],
        pressed_keys={"del_Name_0"},
    )
    assert store.get_suggestions("Demo", "Name") == []

