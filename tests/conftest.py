from __future__ import annotations

import pytest
try:  # pragma: no cover - tiny shim when python-dotenv missing
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover - fallback for minimal test env
    def load_dotenv() -> None:
        """Stub when ``python-dotenv`` is unavailable."""
        return None


@pytest.fixture
def load_env() -> None:
    """Load environment variables from a .env file for tests."""
    load_dotenv()
