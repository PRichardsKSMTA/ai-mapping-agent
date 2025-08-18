import importlib
import json
import sys
from pathlib import Path
from typing import Any


class DummyStreamlit:
    def __init__(
        self,
        *,
        tags_add: dict[str, list[str]] | None = None,
        tags_remove: dict[str, list[str]] | None = None,
    ) -> None:
        """Minimal mock of Streamlit for tag widgets."""

        self.tags_add = tags_add or {}
        self.tags_remove = tags_remove or {}
        self.tag_calls: list[tuple[str, list[str]]] = []

    def dialog(self, *a, **k):
        def wrap(func):
            return func

        return wrap

    def subheader(self, *a, **k) -> None:  # pragma: no cover - trivial
        pass

    def error(self, *a, **k) -> None:  # pragma: no cover - trivial
        pass

    def rerun(self) -> None:  # pragma: no cover - trivial
        pass


def run_dialog(
    monkeypatch,
    tmp_path,
    *,
    suggestions: list[dict] | None = None,
    tags_add: dict[str, list[str]] | None = None,
    tags_remove: dict[str, list[str]] | None = None,
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

    dummy = DummyStreamlit(tags_add=tags_add, tags_remove=tags_remove)

    class DummyTags:
        def __init__(self, parent: DummyStreamlit) -> None:
            self.parent = parent

        def st_tags(
            self, label: str, text: str, value: list[str], key: str, **k: Any
        ) -> list[str]:
            self.parent.tag_calls.append((label, value))
            new_vals = value[:]
            new_vals.extend(self.parent.tags_add.get(key, []))
            for tag in self.parent.tags_remove.get(key, []):
                if tag in new_vals:
                    new_vals.remove(tag)
            return new_vals

    monkeypatch.setitem(sys.modules, "streamlit", dummy)
    monkeypatch.setitem(sys.modules, "streamlit_tags", DummyTags(dummy))
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
    assert ("Columns", ["ColA"]) in dummy.tag_calls


def test_add_suggestion(monkeypatch, tmp_path):
    _, store = run_dialog(
        monkeypatch,
        tmp_path,
        tags_add={"tags_Name": ["ColB"]},
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
        tags_remove={"tags_Name": ["ColA"]},
    )
    assert store.get_suggestions("Demo", "Name") == []

