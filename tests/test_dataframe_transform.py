import types

import pandas as pd
import pytest

from app_utils.dataframe_transform import apply_header_mappings


def test_apply_header_mappings_renames_and_computes():
    template = types.SimpleNamespace(
        layers=[
            types.SimpleNamespace(
                type="header",
                fields=[
                    types.SimpleNamespace(key="X", source="A"),
                    types.SimpleNamespace(key="Y", expression="df['X'] * 2"),
                ],
            )
        ]
    )
    df = pd.DataFrame({"A": [3]})
    out = apply_header_mappings(df, template)
    # Original source column should remain alongside mapped fields
    assert list(out.columns) == ["A", "X", "Y", "Lane ID"]
    assert out.loc[0, "A"] == 3
    assert out.loc[0, "X"] == 3
    assert out.loc[0, "Y"] == 6
    assert out.loc[0, "Lane ID"] == 1


def test_apply_header_mappings_expression_overrides_source():
    template = types.SimpleNamespace(
        layers=[
            types.SimpleNamespace(
                type="header",
                fields=[
                    types.SimpleNamespace(
                        key="B", source="A", expression="df['A'] + 1"
                    )
                ],
            )
        ]
    )
    df = pd.DataFrame({"A": [3]})
    out = apply_header_mappings(df, template)
    # Expression should take precedence over the direct source copy
    assert out.loc[0, "B"] == 4


def test_apply_header_mappings_generates_lane_id():
    template = types.SimpleNamespace(layers=[types.SimpleNamespace(type="header", fields=[])])
    df = pd.DataFrame({"Foo": [10, 20]})
    out = apply_header_mappings(df, template)
    assert out["Lane ID"].tolist() == [1, 2]


def test_apply_header_mappings_coerces_numeric_strings_for_formulas():
    template = types.SimpleNamespace(
        layers=[
            types.SimpleNamespace(
                type="header",
                fields=[
                    types.SimpleNamespace(key="Quotient", expression="df['A'] / df['B']"),
                ],
            )
        ]
    )
    df = pd.DataFrame({"A": ["12", "3.14"], "B": ["3", "0.5"]})
    out = apply_header_mappings(df, template)
    assert out["Quotient"].tolist() == pytest.approx([4.0, 6.28])
    assert out["Quotient"].dtype.kind in {"f", "i"}
