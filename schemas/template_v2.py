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

from pydantic import BaseModel, Field, validator
from typing import List, Literal, Optional, Dict, Any


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
    # strategy: first_available | always
    strategy: Literal["first_available", "always"] = "first_available"
    candidates: Optional[List[Dict[str, Any]]] = None
    expression: Optional[str] = None
    dependencies: Optional[Dict[str, List[str]]] = None


class ComputedLayer(BaseModel):
    type: Literal["computed"]
    sheet: Optional[str] = None
    target_field: str
    formula: ComputedFormula


Layer = HeaderLayer | LookupLayer | ComputedLayer


class Template(BaseModel):
    template_name: str
    layers: List[Layer]

    # Allow additional top-level keys like "fields" or "accounts"
    class Config:
        extra = "allow"

    @validator("layers")
    def at_least_one_layer(cls, value):
        if len(value) == 0:
            raise ValueError("Template must contain at least one layer")
        return value
