import importlib
import json
import pytest
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


def test_add_suggestion_no_replace_on_header(monkeypatch, tmp_path):
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
    assert len(saved) == 2
    assert saved[1]["columns"] == ["ColB"]


def test_add_suggestion_updates_header_id(monkeypatch, tmp_path):
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
    suggestion_store.add_suggestion(base, headers=["A", "B"])
    suggestion_store.add_suggestion(base, headers=["X", "Y"])

    saved = json.loads(path.read_text())
    assert len(saved) == 1
    assert saved[0]["header_id"] == suggestion_store._headers_id(["X", "Y"])


def test_add_suggestion_sets_added(monkeypatch, tmp_path):
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
    saved = json.loads(path.read_text())
    assert saved[0].get("added")
    from datetime import datetime

    datetime.fromisoformat(saved[0]["added"])


def test_display_dedup(monkeypatch, tmp_path):
    path = tmp_path / "mapping_suggestions.json"
    data = [
        {
            "template": "Demo",
            "field": "Zip",
            "type": "direct",
            "formula": None,
            "columns": ["Origin Zip"],
            "display": "Origin Zip",
        },
        {
            "template": "Demo",
            "field": "Zip",
            "type": "direct",
            "formula": None,
            "columns": ["Origin Zip"],
            "display": "origin  zip",
        },
    ]
    path.write_text(json.dumps(data))
    monkeypatch.setenv("SUGGESTION_FILE", str(path))
    importlib.reload(suggestion_store)

    res = suggestion_store.get_suggestions("Demo", "Zip")
    assert len(res) == 1
    assert len(json.loads(path.read_text())) == 1

    suggestion_store.add_suggestion(data[1])
    assert len(json.loads(path.read_text())) == 1


def test_get_suggestions_recency_sort(monkeypatch, tmp_path):
    path = tmp_path / "mapping_suggestions.json"
    data = [
        {
            "template": "Demo",
            "field": "Name",
            "type": "direct",
            "formula": None,
            "columns": ["Old"],
            "display": "Old",
            "added": "2020-01-01T00:00:00+00:00",
        },
        {
            "template": "Demo",
            "field": "Name",
            "type": "direct",
            "formula": None,
            "columns": ["New"],
            "display": "New",
            "added": "2024-01-01T00:00:00+00:00",
        },
        {
            "template": "Demo",
            "field": "Name",
            "type": "direct",
            "formula": None,
            "columns": ["No"],
            "display": "No",
        },
    ]
    path.write_text(json.dumps(data))
    monkeypatch.setenv("SUGGESTION_FILE", str(path))
    importlib.reload(suggestion_store)

    res = suggestion_store.get_suggestions("Demo", "Name")
    assert [s["columns"][0] for s in res] == ["New", "Old", "No"]


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


def test_update_suggestion(monkeypatch, tmp_path):
    path = tmp_path / "mapping_suggestions.json"
    data = [
        {
            "template": "Demo",
            "field": "Name",
            "type": "direct",
            "formula": None,
            "columns": ["ColA"],
            "display": "ColA",
        }
    ]
    path.write_text(json.dumps(data))
    monkeypatch.setenv("SUGGESTION_FILE", str(path))
    importlib.reload(suggestion_store)

    ok = suggestion_store.update_suggestion(
        "Demo",
        "Name",
        columns=[" colA "],
        display="Column B",
        new_columns=["ColB"],
    )
    assert ok
    res = suggestion_store.get_suggestion("Demo", "Name", columns=["ColB"])
    assert res and res["display"] == "Column B"


def test_delete_suggestion(monkeypatch, tmp_path):
    path = tmp_path / "mapping_suggestions.json"
    data = [
        {
            "template": "Demo",
            "field": "Name",
            "type": "direct",
            "formula": None,
            "columns": ["ColA"],
            "display": "ColA",
        },
        {
            "template": "Demo",
            "field": "Name",
            "type": "formula",
            "formula": "A+B",
            "columns": ["ColA", "ColB"],
            "display": "A+B",
        },
    ]
    path.write_text(json.dumps(data))
    monkeypatch.setenv("SUGGESTION_FILE", str(path))
    importlib.reload(suggestion_store)

    removed = suggestion_store.delete_suggestion("Demo", "Name", columns=["colA"])
    assert removed
    remaining = json.loads(path.read_text())
    assert len(remaining) == 1 and remaining[0]["type"] == "formula"

    removed_formula = suggestion_store.delete_suggestion(
        "Demo", "Name", formula="A+B"
    )
    assert removed_formula
    assert json.loads(path.read_text()) == []


@pytest.mark.parametrize(
    "existing",
    [
        [],
        [{"template": "Demo", "field": "Name", "type": "direct", "formula": None, "columns": ["ColA"], "display": "ColA"}],
    ],
)
def test_skip_adhoc_info(monkeypatch, tmp_path, existing):
    path = tmp_path / "mapping_suggestions.json"
    path.write_text(json.dumps(existing))
    monkeypatch.setenv("SUGGESTION_FILE", str(path))
    importlib.reload(suggestion_store)

    s = {
        "template": "Demo",
        "field": "ADHOC_INFO1",
        "type": "direct",
        "formula": None,
        "columns": ["ColA"],
        "display": "ColA",
    }
    suggestion_store.add_suggestion(s)
    assert json.loads(path.read_text()) == existing
    assert suggestion_store.get_suggestions("Demo", "ADHOC_INFO1") == []
    assert suggestion_store.get_suggestion("Demo", "ADHOC_INFO1") is None
