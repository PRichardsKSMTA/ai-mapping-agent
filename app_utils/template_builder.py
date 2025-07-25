from __future__ import annotations

"""Helpers for building minimal template JSON files."""

from typing import Dict, List


def build_header_template(
    template_name: str, columns: List[str], required: Dict[str, bool]
) -> Dict:
    """Return a basic header-only template structure."""
    fields = [
        {"key": col, "required": bool(required.get(col, False))} for col in columns
    ]
    return {
        "template_name": template_name,
        "layers": [
            {
                "type": "header",
                "fields": fields,
            }
        ],
    }
