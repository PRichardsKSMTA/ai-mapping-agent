import argparse
import json
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from schemas.template_v2 import Template
from app_utils.excel_utils import excel_to_json, save_mapped_csv
from app_utils.mapping_utils import suggest_header_mapping, match_lookup_values
from app_utils.mapping.header_layer import apply_gpt_header_fallback
from app_utils.mapping.computed_layer import resolve_computed_layer
from app_utils.mapping.exporter import build_output_template
from app_utils.postprocess_runner import run_postprocess_if_configured


def load_template(path: Path) -> Template:
    with path.open() as f:
        data = json.load(f)
    return Template.model_validate(data)


def load_data(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xls", ".xlsx", ".xlsm"}:
        records, _ = excel_to_json(str(path))
        return pd.DataFrame(records)
    return pd.read_csv(path)


def auto_map(template: Template, df: pd.DataFrame) -> Dict[str, Any]:
    state: Dict[str, Any] = {}
    columns = list(df.columns)
    for idx, layer in enumerate(template.layers):
        if layer.type == "header":
            fields = [f.key for f in layer.fields]  # type: ignore[attr-defined]
            mapping = suggest_header_mapping(fields, columns)
            mapping = apply_gpt_header_fallback(mapping, columns)
            state[f"header_mapping_{idx}"] = mapping
        elif layer.type == "lookup":
            src = layer.source_field
            if src in df.columns:
                unique_vals = sorted(df[src].dropna().unique().astype(str))
                records = getattr(template, layer.dictionary_sheet, [])
                dict_vals = [rec[layer.target_field] for rec in records]
                state[f"lookup_mapping_{idx}"] = match_lookup_values(dict_vals, unique_vals)
        elif layer.type == "computed":
            result = resolve_computed_layer(layer.model_dump(), df)
            state[f"computed_result_{idx}"] = result
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description="Map data to template")
    parser.add_argument("template", type=Path, help="Path to template JSON")
    parser.add_argument("input_file", type=Path, help="Path to CSV/Excel source")
    parser.add_argument("output", type=Path, help="Destination for mapped JSON")
    parser.add_argument(
        "--csv-output",
        type=Path,
        help="Optional path to save mapped CSV",
    )
    args = parser.parse_args()

    template = load_template(args.template)
    df = load_data(args.input_file)
    state = auto_map(template, df)
    mapped = build_output_template(template, state)

    with args.output.open("w") as f:
        json.dump(mapped, f, indent=2)

    if args.csv_output:
        save_mapped_csv(df, mapped, args.csv_output)

    # Trigger optional post-process actions
    run_postprocess_if_configured(template, df)


if __name__ == "__main__":
    main()
