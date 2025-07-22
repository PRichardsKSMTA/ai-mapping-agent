## 0  Current state in one page

| Area                        | Status                                                         | Blocking Pain‑Points                                                |
| --------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------- |
| **Template JSON validator** | Hard‑coded to require `["template_name","fields","accounts"]`  | Fails for any non‑COA template.                                     |
| **UI wizard**               | Fixed 3‑step sequence defined by constant `STEPS`              | Cannot hide the “Match Account Names” step for one‑layer templates. |
| **Mapping helpers**         | Always load `template["accounts"]` and compute embeddings      | Crashes or wastes tokens if that key is missing.                    |
| **Template creation**       | Only manual JSON upload; no Excel‑to‑JSON generator            | Non‑technical users cannot create templates.                        |
| **File structure**          | Monolithic files (`app.py`, duplicated copies)                 | Hard to extend & test independently.                                |

---

## 1  Target architecture (definition of “Done”)

| Layer                      | Goal                                                                                            | “Prove it works by …”                                                                 |
| -------------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| **Template schema v2**     | Only `template_name` & `layers` are mandatory.  Layers can be `header`, `lookup`, `computed`, … | Upload PIT *BID*, Dog‑Breed, or COA template; validator accepts all.                  |
| **Dynamic validator**      | Validate presence/shape of each `layer` object—**not** global keys.                             | Unit tests: `tests/test_validator.py` passes for COA, PIT, and minimal samples.       |
| **Dynamic UI wizard**      | Generate N steps at runtime from `template["layers"]`.                                          | Running the app with PIT shows **one** step; COA shows **two**.                       |
| **Generic mapping engine** | `suggest_layer_mapping(layer, …)` dispatches per layer‑type.                                    | Mapping runs without hitting `KeyError: 'accounts'` on PIT.                           |
| **Template builder**       | “Upload blank template → JSON” wizard in *Template Manager* page.                               | User uploads `PIT User input fields.xlsx`; JSON auto‑appears in sidebar for download. |
| **Modular codebase**       | Utilities split by concern; no file > 300 LoC; tests per module.                                | `pytest` green; new helpers imported without circular refs.                           |
| **AGENTS.md guides**       | One per top‑level folder explaining *purpose, public API, don’ts*.                              | Codex answers “What goes in /app\_utils?” correctly.                                  |

---

## 2  Roadmap ‑ granular tasks & acceptance checks

> **Legend**
> 🔨 = code task for Codex   📄 = doc task   ✅ = manual QA / unit test

### Phase A – Schema & Validator

| #   | Task                                                                                               | Owner | Done‑when                               |
| --- | -------------------------------------------------------------------------------------------------- | ----- | --------------------------------------- |
| A‑1 | 🔨 Create `schemas/template_v2.py` with `pydantic.BaseModel` for `Template`, `Layer`, etc.         | Codex | `pytest -k template_v2` passes.         |
| A‑2 | 🔨 Refactor `Template_Manager.validate_template_json` to use the new model; drop `accounts` check. | Codex | Upload COA & PIT JSONs – both accepted. |
| A‑3 | 📄 Add `docs/template_spec.md` describing layer types & samples.                                   | You   | File committed.                         |

### Phase B – Dynamic Wizard

| #   | Task                                                                                         | Owner | Done‑when                                        |
| --- | -------------------------------------------------------------------------------------------- | ----- | ------------------------------------------------ |
| B‑1 | 🔨 In `app_utils/ui_utils.py` replace global `STEPS` with `build_steps(template_layers)`.    | Codex | PIT run shows 1 step; COA run shows 2.           |
| B‑2 | 🔨 Update `app.py` to iterate over layers generically, calling `render_layer_editor(layer)`. | Codex | No “Match Account Names” step when layer absent. |
| B‑3 | ✅ Smoke‑test header‑only mapping end‑to‑end; download JSON.                                  | You   | File has only `"headers"` key.                   |

### Phase C – Mapping Engine Generalisation

| #   | Task                                                                                 | Owner | Done‑when                                                |
| --- | ------------------------------------------------------------------------------------ | ----- | -------------------------------------------------------- |
| C‑1 | 🔨 Move embedding logic into `lookup_layer.py`; only run for `layer.type=='lookup'`. | Codex | PIT mapping no longer calls OpenAI embeddings.           |
| C‑2 | 🔨 Add support for `computed` layer with `strategy: first_available`.                | Codex | COA template with `computed` layer derives `NET_CHANGE`. |
| C‑3 | ✅ Unit tests for `header`, `lookup`, `computed` strategies.                          | You   | `pytest` suite green.                                    |

### Phase D – Template Builder Wizard

| #   | Task                                                                                | Owner | Done‑when                       |
| --- | ----------------------------------------------------------------------------------- | ----- | ------------------------------- |
| D‑1 | 🔨 Add side‑panel in `Template_Manager.py`: “Upload sample Excel → Detect columns”. | Codex | Columns listed in multi‑select. |
| D‑2 | 🔨 Allow user to flag required columns; save minimal JSON to `/templates`.          | Codex | JSON written; validator passes. |
| D‑3 | ✅ Create template from `PIT User input fields.xlsx`; open in main app.              | You   | Header mapping works.           |

### Phase E – Repo Restructure & Docs

| #   | Task                                                                    | Owner | Done‑when                             |
| --- | ----------------------------------------------------------------------- | ----- | ------------------------------------- |
| E‑1 | 🔨 Split `app_utils` into subpackages: `io`, `mapping`, `ui`, `memory`. | Codex | `import app_utils.io.excel` works.    |
| E‑2 | 📄 Add `AGENTS.md` files (see §3).                                      | Codex | Files present & rendered on GitHub.   |
| E‑3 | ✅ Search repo for TODO/FIXME; no orphaned references to old paths.      | You   | `rg "FIXME"` returns 0 critical hits. |

---

## 3  AGENTS.md skeletons

Create **one file per directory** listed below.  Each should be < 80 lines.

### /AGENTS.md  (root)

```
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
```

### /app\_utils/AGENTS.md

```
# app_utils – Guidelines

| Sub‑module | Responsibility |
|------------|----------------|
| io/        | Reading/writing Excel, CSV, JSON. Pure, side‑effect‑free. |
| mapping/   | Core layer‑wise mapping algorithms. No Streamlit. |
| ui/        | UI widgets / progress indicators. Only Streamlit code. |
| memory/    | Read/write user overrides under `/memories`. |

Don’ts  
* Never import Streamlit outside `ui/`.  
* Never store large DataFrames in `st.session_state`; keep only primitives/metadata.
```

### /pages/AGENTS.md

```
# Streamlit Pages

* Each `.py` renders **one** page.
* Import heavy logic from `app_utils.*`
* Keep per‑page state under keys prefixed with page name to avoid collisions.
```

### /templates/AGENTS.md

```
# Template JSONs

* Must validate against `/schemas/template_v2.py`.
* Only include keys actually needed (no empty arrays).
* Naming: `<template_name>.json` where template_name is kebab‑case.
```

### /tests/AGENTS.md

```
# Tests

* All new logic must have a unit test.
* Use fixtures in `tests/fixtures/`; avoid live API calls (mock OpenAI).
* Target 80 % line coverage.
```

*(Add more AGENTS.md files if you introduce deeper sub‑packages.)*

---

## 4  Immediate Codex task list

You can paste this block in a Codex chat as‑is:

```
### Context
Repo root = ai-mapping-agent (see /AGENTS.md for guidelines).

### Tasks
1. Create schemas/template_v2.py with Pydantic models Template, LayerHeader, LayerLookup, LayerComputed.
2. Refactor Template_Manager.validate_template_json to use the Pydantic model; delete hard‑coded 'accounts' requirement.
3. Add tests/test_validator.py covering COA (old), PIT_BID (header‑only), and DogBreed sample.
4. Replace STEPS constant with dynamic builder in app_utils/ui_utils.py.
5. Generalise mapping_utils: extract embedding code into mapping/lookup_layer.py; determine layer.type at runtime.
6. Commit AGENTS.md files per spec.
```

---

### That’s the full blueprint.

When you re‑enter a new session, you only need to say:

> “Please load the current repo and the roadmap in `ROADMAP.md` (this message). Show me completed vs remaining tasks.”

—and any assistant will be able to continue exactly where you left off.
