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
    monkeypatch.setattr(suggestion_store, "SUGGESTION_FILE", path)

    res = suggestion_store.get_suggestions("demo", "name")
    assert res and res[0]["columns"][0] == "ColA"


def test_add_suggestion_dedup(monkeypatch, tmp_path):
    path = tmp_path / "mapping_suggestions.json"
    path.write_text("[]")
    monkeypatch.setattr(suggestion_store, "SUGGESTION_FILE", path)

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
