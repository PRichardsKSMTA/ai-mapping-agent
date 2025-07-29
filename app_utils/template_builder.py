from __future__ import annotations

"""Helpers for building minimal template JSON files."""

from typing import Dict, List, Tuple
import json
import os
import re
import pandas as pd
from schemas.template_v2 import Template, LookupLayer, ComputedLayer


def slugify(name: str) -> str:
    """Return lowercase kebab-case version of ``name``."""
    slug = re.sub(r"[^0-9a-zA-Z]+", "-", name)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug.lower()


def build_template(
    template_name: str,
    layers: List[Dict],
    postprocess: Dict | None = None,
) -> Dict:
    """Return a validated template structure with arbitrary layers."""
    tpl = {"template_name": template_name, "layers": layers}
    if postprocess:
        tpl["postprocess"] = postprocess
    Template.model_validate(tpl)
    return tpl


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
    header_layer = {"type": "header", "fields": fields}
    return build_template(template_name, [header_layer], postprocess)


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


def gpt_field_suggestions(df: pd.DataFrame) -> Dict[str, str]:
    """Return a mapping {column: 'required'|'optional'|'omit'}."""
    import json
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    client = OpenAI(api_key=api_key)
    system = (
        "Given dataframe columns, decide which should be required in a mapping template. "
        "Return JSON {column: 'required'|'optional'|'omit'} for each column."
    )
    payload = {"columns": list(df.columns)}
    resp = client.chat.completions.create(
        model="gpt-3.5-turbo-0125",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload)},
        ],
        temperature=0.2,
    )
    return json.loads(resp.choices[0].message.content)


def build_lookup_layer(
    source_field: str, target_field: str, dictionary_sheet: str, sheet: str | None = None
) -> Dict:
    """Return a validated lookup layer dict."""
    layer = {
        "type": "lookup",
        "source_field": source_field,
        "target_field": target_field,
        "dictionary_sheet": dictionary_sheet,
    }
    if sheet:
        layer["sheet"] = sheet
    return LookupLayer.model_validate(layer).model_dump(exclude_none=True)


def build_computed_layer(
    target_field: str, expression: str | None = None, sheet: str | None = None
) -> Dict:
    """Return a validated computed layer.

    If ``expression`` is provided the layer uses ``strategy='always'``.
    Otherwise it will be ``strategy='user_defined'`` and the user is expected
    to supply an expression at run-time.
    """

    formula = {"strategy": "always", "expression": expression} if expression else {
        "strategy": "user_defined"
    }
    layer = {
        "type": "computed",
        "target_field": target_field,
        "formula": formula,
    }
    if sheet:
        layer["sheet"] = sheet
    return ComputedLayer.model_validate(layer).model_dump(exclude_none=True)
