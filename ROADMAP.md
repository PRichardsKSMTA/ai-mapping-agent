# AI Mapping Agent – Project Roadmap (MVP)

*Last updated: 2025-07-29*

---

## Legend

✅ Done 🔨 In-progress 🗓 Planned / Not-started

---

## 0  Current state in one page

| Area                        | Status                                                                   | Blocking Pain-Points                                                                      |
| --------------------------- | ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------- |
| **Template JSON validator** | **✅ Dynamic v2 schema live** – validates any layers-only template        | None                                                                                      |
| **UI wizard**               | **✅ Layer-driven** wizard; steps generated at runtime                    | None                                                                                      |
| **Mapping helpers**         | **✅ Modular** – header, lookup, computed helpers in `app_utils/mapping/` | Confidence % display, GPT fallback, and formula dialog with "Suggest formula" GPT helper. |
| **Template creation**       | **🚧 In progress** – Template Manager with GPT field suggestions; supports multi-layer templates and maps headers once | Column detector and save to JSON working. |
| **Post-Process runner**    | 🚧 stage F – base runner implemented; wizard hook pending | Unit tests cover dispatch.
| **File structure**          | **✅ Re-structured** (`io`, `mapping`, `ui`, `pages/steps`)               | —                                                                                         |

---

## 1  Target architecture (definition of “Done”)

| Layer                      | Goal                                                                             | “Prove it works by …”                                |
| -------------------------- | -------------------------------------------------------------------------------- | ---------------------------------------------------- |
| **Template schema v2**     | ✅ implemented & enforced                                                         | COA, PIT\_BID & sample dog-breed templates all load. |
| **Dynamic validator**      | ✅ passes tests                                                                   | `pytest` suite green.                                |
| **Dynamic UI wizard**      | ✅ PIT shows 1 step; COA shows 3 (Header → Lookup → Computed).                    |                                                      |
| **Generic mapping engine** | ✅ lookup embeddings modular; computed resolver working                           | Mapping runs without `KeyError`.                     |
| **Template builder**       | 🚧 stage D – header builder in Template Manager; PIT_BID sample built | GPT-assisted builder still TODO. |
| **Modular codebase**       | ✅ sub-packages & ≤300 LoC per file                                               | Import paths stable.                                 |
| **AGENTS.md guides**       | ✅ committed per top-level folder                                                 | Codex answers architecture questions.                |
| **User-defined fields**    | 🚧 stage F – add-field UI working; `unsaved_changes` flag pending | Reload shows new columns; validator still green. |
| **Post-Process runner**    | 🚧 stage F – base runner implemented; wizard hook pending | Unit tests cover dispatch. |
| **PIT BID flow**           | 🗓 stage G – end-to-end mapping into XLSM + DB                                   | Demo video recorded; integration test passes.        |

---

## 2  Roadmap – granular tasks & acceptance checks

> **Legend**  🔨 code   📄 docs   ✅ QA / test   🚧 in progress   🗓 planned

### Phase A – Schema & Validator (**complete**)

| #   | Task                     | Status |
| --- | ------------------------ | ------ |
| A-1 | Create schema models     | ✅      |
| A-2 | Refactor validator       | ✅      |
| A-3 | Write `template_spec.md` | ✅      |

### Phase B – Dynamic Wizard (**complete**)

| #   | Task                            | Status |
| --- | ------------------------------- | ------ |
| B-1 | Replace global `STEPS`          | ✅      |
| B-2 | Refactor `app.py` to layer loop | ✅      |
| B-3 | Smoke-test header-only mapping  | ✅      |

### Phase C – Mapping UX polish (🔨 Active)

| #     | Task                                                                     | Owner | Done-when                                                    |
| ----- | ------------------------------------------------------------------------ | ----- | ------------------------------------------------------------ |
| C-1   | ✅ Extract lookup embeddings to `lookup_layer.py`                        | Codex | PIT mapping skips embeddings for header-only.                |
| C-1.2 | ✅ Add confidence % display in header & lookup pages                     | Codex | Suggestions show “92 % confident.”                           |
| C-1.3 | ✅ GPT fallback for unmapped lookup values                               | Codex | “Auto-map remaining” fills blanks via GPT.                   |
| C-2   | 🔨 Support computed layer strategies: `first_available` & `user_defined` | Me    | COA sample derives `NET_CHANGE`.                             |
| C-2.1 | ✅ Direct vs Computed toggle UI                                           | Me    | Toggle appears in computed page.                             |
| C-2.2 | ✅ Inline Formula Dialog (free-form + pills + live preview)               | Me    | User can build & preview formulas.                           |
| C-2.3 | ✅ Validate formula on sample rows                                       | Me    | Preview shows values or error only when expression complete. |
| C-2.4 | ✅ Store final expression & include in output JSON                       | Me    | Mapping JSON includes user expression per field.             |
| C-2.5 | ✅ “Suggest formula” helper (GPT-propose)                                | Me    | “Suggest formula” button visible & returns candidate.        |
| C-3   | ✅ Unit tests for all layer strategies                                    | Me    | `pytest` suite green.                                        |
| C-4   | ✅ Fix progress tracker display                              | Codex | Progress bar shows current step and updates per page.        |

### Phase D – Template Builder Wizard (🚧 Active)

| #   | Task                                | Status | Done-when                                 |
| --- | ----------------------------------- | ------ | ----------------------------------------- |
| D-1 | ✅ Column detector sidebar          | Me     | Source columns auto-listed in sidebar.    |
| D-2 | ✅ Mark required fields & save JSON | Me     | “Save as new template…” emits valid JSON. |
| D-3 | ✅ Create PIT BID template JSON     | Me     | File in `templates/` directory.           |
| D-4 | ✅ Dedicated Template Builder page  | Codex  | Step-by-step wizard creates header layer. |
| D-5 | ✅ GPT-assisted field suggestions   | Codex  | Builder proposes required fields.         |
| D-6 | ~~Support lookup & computed layers~~ **superseded** | Codex  | Replaced by runtime layer addition (see D-7). |
| D-7 | 🔨 Runtime addition of lookup & computed layers | Codex  | Builder lets users insert lookup/computed steps on the fly and updates the template JSON. |
| D-6.1 | 🗓 Multi-layer builder | Codex  | Builder allows adding sub-layers; single-header flow uses `standard-fm-coa.json`. |

### Phase E – Docs, packaging & CI (**complete**)

| #   | Task                                                     | Status |
| --- | -------------------------------------------------------- | ------ |
| E-1 | Split `app_utils` into sub-packages                      | ✅      |
| E-2 | Add `AGENTS.md` files                                    | ✅      |
| E-3 | GitHub Actions: `pytest`, `black`, `isort` & smoke tests | ✅      |

### Phase F – User-Defined Fields & Post-Process (🗓 Planned)

| #   | Task                                                                                 | Owner | Done-when                                                                                      |
| --- | ------------------------------------------------------------------------------------ | ----- | ---------------------------------------------------------------------------------------------- |
| F-1 | ✅ Inline “+ Add field” button on Header page                                        | Me    | Users can append/rename/delete destination columns live.                                       |
| F-2 | 🚧 Persist user-defined fields **and runtime layers** into in-memory template; flag `unsaved_changes`; wizard can save updated template | Me    | Reload shows new columns and layers after saving. |
| F-3 | 🔨 Template Manager: “Save as new template…” UI + write metadata to DB (reuse wizard save logic)             | Codex | Persists template JSON + metadata row in `dbo.MAPPING_AGENT_PROCESSES`.                        |
| F-3.1 | ✅ Build dedicated Template Manager page; move features off sidebar | Codex | Template Manager page provides upload/download/delete UI without sidebar items. |
| F-4 | ✅ Extend schema v2.3: optional top-level `"postprocess"` object                     | Codex | Validator green; spec updated in `template_spec.md`.                                           |
| F-5 | ✅ `postprocess_runner.py`: dispatch run types (`python_script`, `pit_bid_excel`)    | Codex | Unit tests cover each run type.                                                                |
| F-6 | 🔨 Wizard “Run Export” step: generate `process_guid`, run post-process, capture logs | Codex | Output JSON includes `process_guid`; DB rows in `RFP_OBJECT_DATA` & `MAPPING_AGENT_PROCESSES`. |
| F-7 | 🗓 Extend schema v2.2: refine `user_defined` formulas for runtime layers | Codex | Validator green with new field; docs updated. |

### Phase G – PIT BID template & flow (🗓 Planned)

| #   | Task                                                                   | Owner | Done-when                                     |
| --- | ---------------------------------------------------------------------- | ----- | --------------------------------------------- |
| G-1 | End-to-end mapping: upload sample RFP → fill PIT XLSM → insert into DB | Me    | Demo video recorded; integration test passes. |

---

## 3  AGENTS.md skeletons

Create **one file per directory** listed below. Each should be < 80 lines.

### /AGENTS.md (root)

```
# AI Mapping Agent – Root Playbook

## Mission
Provide a template-agnostic data-mapping toolkit usable from Streamlit, CLI, or Azure Functions.

## Sub-dirs
* `app_utils/` – Core business logic (I/O, mapping, UI helpers, memory).
* `pages/` – Streamlit pages; keep UI only, no heavy logic.
* `templates/` – JSON template definitions; validated against `schemas/template_v2.py`.
* `tests/` – PyTest suites; fast, deterministic.

## Conventions
* Use type hints everywhere.
* No file > 300 logical lines.
* External services behind feature flags (`OPENAI_API_KEY`, etc.).
```

### /app\_utils/AGENTS.md

```
# app_utils – Guidelines

| Sub-module | Responsibility                                      |
|------------|-----------------------------------------------------|
| io/        | Reading/writing Excel, CSV, JSON. Pure, side-effect-free. |
| mapping/   | Core layer-wise mapping algorithms. No Streamlit.   |
| ui/        | UI widgets / progress indicators. Only Streamlit code. |
| memory/    | Read/write user overrides under `/memories`.        |

Don’ts  
* Never import Streamlit outside `ui/`.  
* Never store large DataFrames in `st.session_state`; keep only primitives/metadata.
```

### /pages/AGENTS.md

```
# Streamlit Pages

* Each `.py` renders **one** page.
* Import heavy logic from `app_utils.*`
* Keep per-page state under keys prefixed with page name to avoid collisions.
```

### /templates/AGENTS.md

```
# Template JSONs

* Must validate against `/schemas/template_v2.py`.
* Only include keys actually needed (no empty arrays).
* Naming: `<template_name>.json` where template_name is kebab-case.
```

### /tests/AGENTS.md

```
# Tests

* All new logic must have a unit test.
* Use fixtures in `tests/fixtures/`; avoid live API calls (mock OpenAI).
* Target 80 % line coverage.
```

*(Add more AGENTS.md files if you introduce deeper sub-packages.)*

---

## 4  Immediate Codex task list (updated)

```
### Context
Repo root = ai-mapping-agent (see /AGENTS.md for guidelines).

### Tasks
1. Runtime addition of lookup & computed layers (D-7).
2. Track `unsaved_changes` for added fields and layers (F-2).
3. Wire postprocess runner into wizard (F-6).

```

---

## 5  Current File Structure

```
└── 📁ai-mapping-agent
    ├── 📁app_utils
    │   ├── 📁io
    │   ├── 📁mapping
    │   ├── 📁ui
    │   ├── 📁memory
    │   ├── AGENTS.md
    │   └── ...
    ├── 📁docs
    │   ├── template_spec.md
    │   └── ...
    ├── 📁pages
    │   ├── steps
    │   │   ├── header.py
    │   │   ├── lookup.py
    │   │   └── computed.py
    │   ├── template_manager.py
    │   └── AGENTS.md
    ├── 📁schemas
    │   ├── template_v2.py
    │   └── ...
    ├── 📁templates
    │   ├── standard-fm-coa.json
    │   └── AGENTS.md
    ├── 📁tests
    │   ├── test_validator.py
    │   ├── test_excel_to_json.py
    │   └── AGENTS.md
    ├── .env
    ├── app.py
    ├── AGENTS.md
    ├── ROADMAP.md
    ├── requirements.txt
    └── README.md
```