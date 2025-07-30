from __future__ import annotations
"""Build final template JSON with user choices."""

from copy import deepcopy
from typing import Any, Dict, MutableMapping

from schemas.template_v2 import Template
from .computed_layer import persist_expression_from_state


def _apply_header_expressions(layer: Dict[str, Any], idx: int, state: MutableMapping[str, Any]) -> Dict[str, Any]:
    new_layer = deepcopy(layer)
    mapping = state.get(f"header_mapping_{idx}", {})

    # include any extra fields added by the user
    extras = state.get(f"header_extra_fields_{idx}", [])
    for name in extras:
        if not any(f.get("key") == name for f in new_layer.get("fields", [])):
            new_layer.setdefault("fields", []).append({"key": name, "required": False})

    for field in new_layer.get("fields", []):
        info = mapping.get(field["key"], {})
        if "src" in info:
            field["source"] = info["src"]
        if "expr" in info:
            field["expression"] = info["expr"]
    return new_layer


def _apply_lookup_mapping(layer: Dict[str, Any], idx: int, state: MutableMapping[str, Any]) -> Dict[str, Any]:
    """Attach user-defined value mappings to ``layer`` if present."""
    new_layer = deepcopy(layer)
    mapping = state.get(f"lookup_mapping_{idx}")
    if mapping:
        new_layer["mapping"] = mapping
    return new_layer


def build_output_template(
    template: Template,
    state: MutableMapping[str, Any],
    process_guid: str | None = None,
) -> Dict[str, Any]:
    """Return template JSON enriched with user expressions."""
    tpl = deepcopy(template.model_dump())
    layers = []
    for idx, layer in enumerate(tpl.get("layers", [])):
        if layer.get("type") == "header":
            layers.append(_apply_header_expressions(layer, idx, state))
        elif layer.get("type") == "lookup":
            layers.append(_apply_lookup_mapping(layer, idx, state))
        elif layer.get("type") == "computed":
            layers.append(persist_expression_from_state(layer, idx, state))
        else:
            layers.append(layer)
    tpl["layers"] = layers
    if process_guid:
        tpl["process_guid"] = process_guid
    return tpl
