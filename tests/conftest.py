from __future__ import annotations

import os
from pathlib import Path
import pytest
try:  # pragma: no cover - tiny shim when python-dotenv missing
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover - fallback for minimal test env
    def load_dotenv() -> None:
        """Stub when ``python-dotenv`` is unavailable."""
        return None

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - safety for older Python
    tomllib = None  # type: ignore


@pytest.fixture
def load_env() -> None:
    """Load environment variables from `.env` and secrets for tests."""
    load_dotenv()
    secrets_path = Path(".streamlit/secrets.toml")
    if tomllib and secrets_path.exists():
        with secrets_path.open("rb") as fh:
            secrets = tomllib.load(fh)
        for key, value in secrets.items():
            os.environ.setdefault(key, str(value))
