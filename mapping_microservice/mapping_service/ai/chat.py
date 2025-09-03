from __future__ import annotations

"""Simple OpenAI chat helper returning parsed JSON."""

import json
import os
from typing import Any, Dict

from openai import OpenAI


def chat_json(system: str, payload: Dict[str, Any], *, model: str = "gpt-4o-mini", temperature: float = 0.2) -> Any:
    """Send a chat completion request and parse the JSON response."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload)},
        ],
        temperature=temperature,
    )
    content = resp.choices[0].message.content
    return json.loads(content)
