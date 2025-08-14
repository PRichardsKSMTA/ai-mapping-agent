import logging

from app_utils import user_prefs


def test_set_and_get_last_template(tmp_path, monkeypatch):
    pref = tmp_path / "prefs.json"
    monkeypatch.setattr(user_prefs, "USER_PREFS_FILE", pref)

    user_prefs.set_last_template("u@example.com", "demo.json")
    assert pref.exists()
    assert user_prefs.get_last_template("u@example.com") == "demo.json"

    user_prefs.set_last_template("u@example.com", "")
    assert user_prefs.get_last_template("u@example.com") is None


def test_load_empty_file(tmp_path, monkeypatch, caplog):
    pref = tmp_path / "prefs.json"
    pref.write_text("")
    monkeypatch.setattr(user_prefs, "USER_PREFS_FILE", pref)

    with caplog.at_level(logging.WARNING):
        assert user_prefs._load() == {}


def test_load_malformed_file(tmp_path, monkeypatch, caplog):
    pref = tmp_path / "prefs.json"
    pref.write_text("{ bad json }")
    monkeypatch.setattr(user_prefs, "USER_PREFS_FILE", pref)

    with caplog.at_level(logging.WARNING):
        assert user_prefs._load() == {}
