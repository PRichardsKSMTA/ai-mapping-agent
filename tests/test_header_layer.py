import json
import os
from app_utils.mapping.header_layer import gpt_header_completion, apply_gpt_header_fallback


def test_gpt_header_completion(monkeypatch):
    class FakeResp:
        def __init__(self, content):
            self.choices = [type("c", (), {"message": type("m", (), {"content": content})()})()]

    class FakeCompletions:
        def create(self, model, messages, temperature):
            data = {"FieldA": "ColA"}
            return FakeResp(json.dumps(data))

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = type("chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr("app_utils.mapping.header_layer.OpenAI", lambda api_key=None: FakeClient())
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    res = gpt_header_completion(["FieldA"], ["ColA", "ColB"])
    assert res == {"FieldA": "ColA"}


def test_apply_gpt_header_fallback(monkeypatch):
    def fake_completion(unmapped, columns):
        return {"FieldB": "ColB"}

    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(
        "app_utils.mapping.header_layer.gpt_header_completion", fake_completion
    )

    mapping = {"FieldA": {"src": "ColA"}, "FieldB": {}}
    out = apply_gpt_header_fallback(mapping, ["ColA", "ColB"], targets=["FieldB"])
    assert out["FieldB"]["src"] == "ColB"


def test_apply_gpt_header_fallback_skips_adhoc(monkeypatch):
    def fake_completion(unmapped, columns):
        # ``ADHOC_INFO`` fields must never be sent to GPT or pre-filled.
        assert "ADHOC_INFO1" not in unmapped
        return {"ADHOC_INFO1": "ColC"}

    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(
        "app_utils.mapping.header_layer.gpt_header_completion", fake_completion
    )

    mapping = {"ADHOC_INFO1": {}, "FieldA": {"src": "ColA"}}
    out = apply_gpt_header_fallback(mapping, ["ColA", "ColC"])
    assert "src" not in out["ADHOC_INFO1"]

