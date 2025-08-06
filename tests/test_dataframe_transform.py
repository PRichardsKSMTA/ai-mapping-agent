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
    assert list(out.columns) == ["X", "Y"]
    assert out.loc[0, "X"] == 3
    assert out.loc[0, "Y"] == 6
