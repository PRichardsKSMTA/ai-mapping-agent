"""
Shared OpenAI embedding helper with in-memory LRU cache.
"""

from __future__ import annotations
from functools import lru_cache
from typing import List
import os

import openai  # type: ignore

MODEL = "text-embedding-3-small"


@lru_cache(maxsize=8192)
def embed(text: str) -> List[float]:
    """Return embedding vector; caches identical inputs."""
    if "OPENAI_API_KEY" not in os.environ:
        raise RuntimeError("OPENAI_API_KEY not set")
    return (
        openai.embeddings.create(model=MODEL, input=[text]).data[0].embedding  # type: ignore
    )
