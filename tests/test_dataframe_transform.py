import types
import pandas as pd

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
    assert list(out.columns) == ["A", "X", "Y"]
    assert out.loc[0, "A"] == 3
    assert out.loc[0, "X"] == 3
    assert out.loc[0, "Y"] == 6


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
