from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Optional

USER_PREFS_FILE = Path("data/user_prefs.json")
logger = logging.getLogger(__name__)


def _load() -> Dict[str, str]:
    if not USER_PREFS_FILE.exists():
        return {}
    try:
        return json.loads(USER_PREFS_FILE.read_text())
    except json.JSONDecodeError:
        logger.warning("user prefs file %s is not valid JSON", USER_PREFS_FILE)
        return {}


def _save(data: Dict[str, str]) -> None:
    USER_PREFS_FILE.parent.mkdir(exist_ok=True, parents=True)
    USER_PREFS_FILE.write_text(json.dumps(data, indent=2))


def get_last_template(user_email: str) -> Optional[str]:
    return _load().get(user_email)


def set_last_template(user_email: str, template_file: str) -> None:
    data = _load()
    if template_file:
        data[user_email] = template_file
    else:
        data.pop(user_email, None)
    _save(data)
