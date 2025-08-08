"""
Pydantic models for template-agnostic mapping.

A template **must** have:
• template_name: str
• layers: list[Layer]

Each Layer has its own `type` and shape:
    - HeaderLayer:   {"type": "header",  fields: [...]}
    - LookupLayer:   {"type": "lookup",  source_field: str, target_field: str, dictionary: str}
    - ComputedLayer: {"type": "computed", target_field: str, formula: {...}}

Extra properties are preserved (`extra = "allow"`) so future
layer types can be added without changing the model.
"""

from __future__ import annotations

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    ConfigDict,
    ValidationError,
    HttpUrl,
)
from typing import List, Literal, Optional, Dict, Any
from uuid import UUID


class FieldSpec(BaseModel):
    key: str
    type: Optional[str] = Field(
        default="string",
        description="Primitive type hint; optional for header-only templates",
    )
    required: bool = False
    notes: Optional[str] = None


class HeaderLayer(BaseModel):
    type: Literal["header"]
    sheet: Optional[str] = None
    fields: List[FieldSpec]


class LookupLayer(BaseModel):
    type: Literal["lookup"]
    sheet: Optional[str] = None
    source_field: str
    target_field: str
    dictionary_sheet: str


class ComputedFormula(BaseModel):
    # strategy: first_available | user_defined | always
    strategy: Literal["first_available", "user_defined", "always"] = "first_available"
    candidates: Optional[List[Dict[str, Any]]] = None
    expression: Optional[str] = None
    dependencies: Optional[Dict[str, List[str]]] = None


class ComputedLayer(BaseModel):
    type: Literal["computed"]
    sheet: Optional[str] = None
    target_field: str
    formula: ComputedFormula


class PostprocessSpec(BaseModel):
    """Optional POST request instructions."""

    url: HttpUrl


Layer = HeaderLayer | LookupLayer | ComputedLayer


class Template(BaseModel):
    template_guid: Optional[str] = Field(
        default=None, description="Unique identifier for this template"
    )
    template_name: str
    layers: List[Layer]
    postprocess: Optional[PostprocessSpec] = None

    # Allow unknown top-level keys (back-compat)
    model_config = ConfigDict(extra="allow")

    # Pydantic-v2 syle validator
    @field_validator("template_guid")
    @classmethod
    def _valid_guid(cls, v: Optional[str]):
        if v is None:
            return v
        UUID(v)
        return v

    @field_validator("layers")
    @classmethod
    def _non_empty_layers(cls, v: List[Layer]):
        if not v:
            raise ValueError("Template must contain at least one layer")
        return v
