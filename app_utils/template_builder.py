from __future__ import annotations

"""Helpers for building minimal template JSON files."""

from typing import Dict, List, Tuple
import json
import os
import re
from schemas.template_v2 import Template


def slugify(name: str) -> str:
    """Return lowercase kebab-case version of ``name``."""
    slug = re.sub(r"[^0-9a-zA-Z]+", "-", name)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug.lower()


def build_header_template(
    template_name: str,
    columns: List[str],
    required: Dict[str, bool],
    postprocess: Dict | None = None,
) -> Dict:
    """Return a basic header-only template structure."""
    fields = [
        {"key": col, "required": bool(required.get(col, False))} for col in columns
    ]
    tpl = {
        "template_name": template_name,
        "layers": [
            {
                "type": "header",
                "fields": fields,
            }
        ],
    }
    if postprocess:
        tpl["postprocess"] = postprocess
    return tpl


def load_template_json(uploaded) -> Dict:
    """Load and validate a template JSON uploaded file."""
    data = json.load(uploaded)
    Template.model_validate(data)
    return data


def save_template_file(tpl: Dict, directory: str = "templates") -> str:
    """Save validated template to templates/<name>.json and return name."""
    safe = slugify(tpl["template_name"])
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{safe}.json")
    with open(path, "w") as f:
        json.dump(tpl, f, indent=2)
    return safe


def apply_field_choices(
    columns: List[str], choices: Dict[str, str]
) -> Tuple[List[str], Dict[str, bool]]:
    """Return filtered columns and required map based on user choices."""
    selected = [c for c in columns if choices.get(c) != "omit"]
    required = {c: choices.get(c) == "required" for c in selected}
    return selected, required

