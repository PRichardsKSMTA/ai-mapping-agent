from __future__ import annotations

"""Helper functions for the header mapping UI."""

import re
import streamlit as st
from app_utils.suggestion_store import add_suggestion, remove_suggestion
from app_utils.template_builder import (
    build_lookup_layer,
    build_computed_layer,
    save_template_file,
)
from app_utils.ui_utils import set_steps_from_template


def set_field_mapping(field_key: str, idx: int, value: dict) -> None:
    """Persist mapping for ``field_key``."""
    map_key = f"header_mapping_{idx}"
    mapping = st.session_state.setdefault(map_key, {})
    if mapping.get(field_key) != value:
        mapping[field_key] = value
        st.session_state[map_key] = mapping


def remove_formula(field_key: str, idx: int, drop_suggestion: bool = False) -> None:
    """Remove formula mapping for ``field_key`` and optionally drop suggestion."""
    map_key = f"header_mapping_{idx}"
    mapping = st.session_state.get(map_key, {})
    info = mapping.get(field_key, {})
    info.pop("expr", None)
    info.pop("expr_display", None)
    mapping[field_key] = info
    st.session_state[map_key] = mapping
    tpl = st.session_state.get("current_template")
    if tpl and drop_suggestion:
        remove_suggestion(tpl, field_key, "formula")


def remove_field(field_key: str, idx: int) -> None:
    """Delete a user-added field from session state."""
    map_key = f"header_mapping_{idx}"
    extra_key = f"header_extra_fields_{idx}"
    mapping = st.session_state.get(map_key, {})
    mapping.pop(field_key, None)
    st.session_state[map_key] = mapping
    extras = st.session_state.get(extra_key, [])
    if field_key in extras:
        extras.remove(field_key)
        st.session_state[extra_key] = extras
    tpl = st.session_state.get("template")
    if tpl:
        layer = tpl["layers"][idx]
        layer["fields"] = [
            f for f in layer.get("fields", []) if f.get("key") != field_key
        ]
        st.session_state["template"] = tpl
    st.session_state["unsaved_changes"] = True


def add_field(field_key: str, idx: int) -> None:
    """Append a new field to session state and template."""
    map_key = f"header_mapping_{idx}"
    extra_key = f"header_extra_fields_{idx}"
    mapping = st.session_state.setdefault(map_key, {})
    mapping[field_key] = {}
    st.session_state[map_key] = mapping
    extras = st.session_state.setdefault(extra_key, [])
    if field_key not in extras:
        extras.append(field_key)
        st.session_state[extra_key] = extras
    tpl = st.session_state.get("template")
    if tpl:
        layer = tpl["layers"][idx]
        if not any(f.get("key") == field_key for f in layer.get("fields", [])):
            layer.setdefault("fields", []).append({"key": field_key, "required": False})
        st.session_state["template"] = tpl
    st.session_state["unsaved_changes"] = True


def append_lookup_layer(
    source_field: str,
    target_field: str,
    dictionary_sheet: str,
    sheet: str | None = None,
) -> None:
    """Append a lookup layer to the in-memory template."""
    tpl = st.session_state.get("template")
    if not tpl:
        return
    layer = build_lookup_layer(
        source_field, target_field, dictionary_sheet, sheet=sheet
    )
    tpl.setdefault("layers", []).append(layer)
    st.session_state["template"] = tpl
    set_steps_from_template(tpl["layers"])
    st.session_state["unsaved_changes"] = True


def append_computed_layer(
    target_field: str, expression: str, sheet: str | None = None
) -> None:
    """Append a computed layer to the in-memory template."""
    tpl = st.session_state.get("template")
    if not tpl:
        return
    layer = build_computed_layer(target_field, expression, sheet=sheet)
    tpl.setdefault("layers", []).append(layer)
    st.session_state["template"] = tpl
    set_steps_from_template(tpl["layers"])
    st.session_state["unsaved_changes"] = True


def save_current_template() -> str | None:
    """Save ``st.session_state['template']`` using ``save_template_file``."""
    tpl = st.session_state.get("template")
    if not tpl:
        return None
    name = save_template_file(tpl)
    st.session_state["unsaved_changes"] = False
    return name


def persist_suggestions_from_mapping(layer, mapping: dict, source_cols: list[str]) -> None:
    """Persist suggestions for the provided mapping."""
    template = st.session_state.get("current_template")
    if template is None:
        return
    for field in layer.fields:  # type: ignore
        key: str = field.key
        if key.startswith("ADHOC_INFO"):
            continue
        info = mapping.get(key, {})
        if "src" in info:
            add_suggestion(
                {
                    "template": template,
                    "field": field.key,
                    "type": "direct",
                    "formula": None,
                    "columns": [info["src"]],
                    "display": info["src"],
                },
                headers=source_cols,
            )
        elif "expr" in info:
            cols = re.findall(r"df\['([^']+)'\]", info["expr"])
            add_suggestion(
                {
                    "template": template,
                    "field": field.key,
                    "type": "formula",
                    "formula": info["expr"],
                    "columns": cols,
                    "display": info.get("expr_display", info["expr"]),
                },
                headers=source_cols,
            )

