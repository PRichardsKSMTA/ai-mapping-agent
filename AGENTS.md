# AI Mapping Agent – Root Playbook

## Mission
Provide a template‑agnostic data‑mapping toolkit usable from Streamlit, CLI, or Azure Functions.

## Sub‑dirs
* `app_utils/` – Core business logic (I/O, mapping, UI helpers, memory).
* `pages/`     – Streamlit pages; keep UI only, no heavy logic.
* `templates/` – JSON template definitions; validated against `schemas/template_v2.py`.
* `tests/`     – PyTest suites; fast, deterministic.

## Conventions
* Use type hints everywhere.
* No file > 300 logical lines.
* External services behind feature flags (`OPENAI_API_KEY`, etc.).
