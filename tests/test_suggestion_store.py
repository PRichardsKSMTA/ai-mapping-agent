import importlib
import json
from app_utils import suggestion_store


def test_get_suggestions_canonical(monkeypatch, tmp_path):
    path = tmp_path / "mapping_suggestions.json"
    data = [
        {
            "template": "Demo",
            "field": " Name ",
            "type": "direct",
            "formula": None,
            "columns": ["ColA"],
            "display": "ColA",
        }
    ]
    path.write_text(json.dumps(data))
    monkeypatch.setenv("SUGGESTION_FILE", str(path))
    importlib.reload(suggestion_store)

    res = suggestion_store.get_suggestions("demo", "name")
    assert res and res[0]["columns"][0] == "ColA"


def test_add_suggestion_dedup(monkeypatch, tmp_path):
    path = tmp_path / "mapping_suggestions.json"
    path.write_text("[]")
    monkeypatch.setenv("SUGGESTION_FILE", str(path))
    importlib.reload(suggestion_store)

    base = {
        "template": "Demo",
        "field": "Name",
        "type": "direct",
        "formula": None,
        "columns": ["ColA"],
        "display": "ColA",
    }
    suggestion_store.add_suggestion(base)
    suggestion_store.add_suggestion({**base, "field": " name ", "columns": ["colA"]})

    saved = json.loads(path.read_text())
    assert len(saved) == 1


def test_add_suggestion_replace_on_header(monkeypatch, tmp_path):
    path = tmp_path / "mapping_suggestions.json"
    path.write_text("[]")
    monkeypatch.setenv("SUGGESTION_FILE", str(path))
    importlib.reload(suggestion_store)

    base = {
        "template": "Demo",
        "field": "Name",
        "type": "direct",
        "formula": None,
        "columns": ["ColA"],
        "display": "ColA",
    }
    headers = ["ColA", "ColB"]
    suggestion_store.add_suggestion(base, headers=headers)
    suggestion_store.add_suggestion({**base, "columns": ["ColB"]}, headers=headers)

    saved = json.loads(path.read_text())
    assert len(saved) == 1
    assert saved[0]["columns"] == ["ColB"]


def test_round_trip_persistence(monkeypatch, tmp_path):
    path = tmp_path / "data" / "mapping_suggestions.json"
    monkeypatch.setenv("SUGGESTION_FILE", str(path))
    importlib.reload(suggestion_store)

    base = {
        "template": "Demo",
        "field": "Name",
        "type": "direct",
        "formula": None,
        "columns": ["ColA"],
        "display": "ColA",
    }
    suggestion_store.add_suggestion(base)
    assert path.exists()

    importlib.reload(suggestion_store)
    res = suggestion_store.get_suggestions("Demo", "Name")
    assert res and res[0]["columns"] == ["ColA"]
