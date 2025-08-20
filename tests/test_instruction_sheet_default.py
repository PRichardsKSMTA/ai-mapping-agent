import app


def test_instruction_sheet_not_default():
    sheets = ["Instructions", "Data"]
    idx = app.default_sheet_index(sheets)
    assert idx == 1

    session_state: dict[str, str] = {}
    captured: dict[str, list[str] | int] = {}

    def fake_selectbox(label: str, options: list[str], index: int, key: str) -> str:
        captured["options"] = options
        captured["index"] = index
        session_state[key] = options[index]
        return options[index]

    sheet_key = "upload_sheet"
    if len(sheets) > 1:
        fake_selectbox("Select sheet", sheets, idx, sheet_key)
    if sheet_key not in session_state:
        session_state[sheet_key] = sheets[idx]

    assert session_state[sheet_key] == "Data"
    assert "Instructions" in captured["options"]
