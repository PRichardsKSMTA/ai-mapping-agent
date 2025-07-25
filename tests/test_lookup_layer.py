import json
import os
import openai
from app_utils.mapping.lookup_layer import gpt_lookup_completion


def test_gpt_lookup_completion(monkeypatch):
    class FakeResp:
        def __init__(self, content):
            self.choices = [type("c", (), {"message": type("m", (), {"content": content})()})()]

    class FakeCompletions:
        def create(self, model, messages, temperature):
            data = {"A": "B"}
            return FakeResp(json.dumps(data))

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = type("chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr(openai, "OpenAI", lambda api_key=None: FakeClient())
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    res = gpt_lookup_completion(["A"], ["B", "C"])
    assert res == {"A": "B"}

