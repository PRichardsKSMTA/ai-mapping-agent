import json

import pandas as pd

from app_utils.mapping.computed_layer import gpt_formula_suggestion


def test_gpt_formula_suggestion(monkeypatch):
    class FakeResp:
        def __init__(self, content):
            self.choices = [
                type("c", (), {"message": type("m", (), {"content": content})()})()
            ]

    class FakeCompletions:
        def create(self, model, messages, temperature):
            return FakeResp("df['A'] + df['B']")

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = type("chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(
        "app_utils.mapping.computed_layer.OpenAI",
        lambda api_key=None: FakeClient(),
    )

    df = pd.DataFrame({"A": [1], "B": [2]})
    expr = gpt_formula_suggestion("NET_CHANGE", df)
    assert expr == "df['A'] + df['B']"
