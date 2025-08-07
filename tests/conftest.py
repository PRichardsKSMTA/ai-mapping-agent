from __future__ import annotations

import pytest
from dotenv import load_dotenv


@pytest.fixture
def load_env() -> None:
    """Load environment variables from a .env file for tests."""
    load_dotenv()
