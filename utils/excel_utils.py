import pandas as pd # type: ignore

def detect_header_row(path: str,
                      sheet_name=0,
                      max_rows=50,
                      min_non_empty_ratio=0.5):
    """
    Scan the first `max_rows` rows without headers,
    pick the row index with the highest non-empty ratio ≥ min_non_empty_ratio.
    """
    df_preview = pd.read_excel(path,
                               sheet_name=sheet_name,
                               header=None,
                               nrows=max_rows)
    total_cols = df_preview.shape[1]
    best_idx, best_ratio = None, 0

    for idx, row in df_preview.iterrows():
        non_empty = row.count()
        ratio = non_empty / total_cols
        if ratio > best_ratio and ratio >= min_non_empty_ratio:
            best_idx, best_ratio = idx, ratio

    return best_idx if best_idx is not None else 0


def excel_to_json(path: str,
                  sheet_name=0,
                  max_rows=50,
                  min_non_empty_ratio=0.5):
    """
    1) Detect primary header row.
    2) If the row above it also passes the non-empty threshold, 
       read both as a multi-row header.
    3) Flatten into single-level column names.
    4) Drop blank rows and return JSON records + column list.
    """
    # 1) Find the “best” header row
    header_row = detect_header_row(path, sheet_name, max_rows, min_non_empty_ratio)

    # 2) Peek at the row above to see if it’s also a header row
    df_preview = pd.read_excel(path,
                               sheet_name=sheet_name,
                               header=None,
                               nrows=header_row + 1)
    total_cols = df_preview.shape[1]
    header_rows = [header_row]

    if header_row > 0:
        prev_non_empty = df_preview.iloc[header_row - 1].count()
        if (prev_non_empty / total_cols) >= min_non_empty_ratio:
            header_rows = [header_row - 1, header_row]

    # 3) Read the full sheet using one- or two-row header
    df = pd.read_excel(path,
                       sheet_name=sheet_name,
                       header=header_rows)

    # 4) Flatten MultiIndex if present
    if isinstance(df.columns, pd.MultiIndex):
        flat_cols = []
        for col_tuple in df.columns:
            parts = [
                str(part).strip()
                for part in col_tuple
                if pd.notna(part) and str(part).strip() != ""
            ]
            flat_cols.append(" ".join(parts))
        df.columns = flat_cols
    else:
        df.columns = df.columns.map(str)

    # 5) Clean and return
    df = df.dropna(how="all")
    return df.to_dict(orient="records"), list(df.columns)
