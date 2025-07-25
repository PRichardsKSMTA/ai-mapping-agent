# AI Mapping Agent – Root Playbook

## Mission
Provide a template‑agnostic data‑mapping toolkit usable from Streamlit, CLI, or Azure Functions.

## Sub‑dirs
* `app_utils/` – Core business logic (I/O, mapping, AI helpers, UI widgets).
* `pages/`     – Streamlit pages; dynamic wizard under `pages/steps`.
* `templates/` – JSON template definitions; validated via `schemas/template_v2.py`.
* `tests/`     – PyTest suites; fast and deterministic.

## Current milestone
* Dynamic mapping wizard operational (header → lookup → computed).
* Template Builder UI underway (see ROADMAP phase D).
* Post‑process runner still planned for phase F.

## Conventions
* Use type hints everywhere.
* No file > 300 logical lines.
* External services behind feature flags (`OPENAI_API_KEY`, etc.).
