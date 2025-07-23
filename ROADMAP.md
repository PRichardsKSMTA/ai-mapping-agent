## 0  Current state in one page

| Area                        | Status                                                                   | Blocking Pain‑Points                                        |
| --------------------------- | ------------------------------------------------------------------------ | ----------------------------------------------------------- |
| **Template JSON validator** | **✅ Dynamic v2 schema live** – validates any layers‑only template        | None – back‑compat with v1 templates intentionally dropped. |
| **UI wizard**               | **✅ Layer‑driven** wizard; steps generated at runtime                    | None                                                        |
| **Mapping helpers**         | **✅ Modular** – header, lookup, computed helpers in `app_utils/mapping/` | Confidence % and GPT fallback still to add.                 |
| **Template creation**       | **🚧 In progress** – wizard skeleton exists; GPT‑builder not yet wired   | Needs column detector + save.                               |
| **File structure**          | **✅ Re‑structured** (`io`, `mapping`, `ui`, `pages/steps`)               | —                                                           |

---

## 1  Target architecture (definition of “Done”)

| Layer                      | Goal                                                          | “Prove it works by …”                                |
| -------------------------- | ------------------------------------------------------------- | ---------------------------------------------------- |
| **Template schema v2**     | ✅ implemented & enforced                                      | COA, PIT\_BID & sample dog‑breed templates all load. |
| **Dynamic validator**      | ✅ passes tests                                                | `pytest` green.                                      |
| **Dynamic UI wizard**      | ✅ PIT shows 1 step; COA shows 3 (Header → Lookup → Computed). |                                                      |
| **Generic mapping engine** | ✅ lookup embeddings modular; computed resolver working        | Mapping runs without `KeyError`.                     |
| **Template builder**       | 🚧 stage D – column detector UI drafted                       | Auto JSON dump still TODO.                           |
| **Modular codebase**       | ✅ sub‑packages & ≤300 LoC per file                            | Import paths stable.                                 |
| **AGENTS.md guides**       | ✅ committed per top‑level folder                              | Codex answers architecture questions.                |

---

## 2  Roadmap – granular tasks & acceptance checks

> **Legend**  🔨 code   📄 docs   ✅ QA / test   🚧 in progress   🆕 new task

### Phase A – Schema & Validator (**complete**)

| #   | Task                    | Status |
| --- | ----------------------- | ------ |
| A‑1 | Create schema models    | ✅      |
| A‑2 | Refactor validator      | ✅      |
| A‑3 | Write template\_spec.md | ✅      |

### Phase B – Dynamic Wizard (**complete**)

| #   | Task                            | Status |
| --- | ------------------------------- | ------ |
| B‑1 | Replace global `STEPS`          | ✅      |
| B‑2 | Refactor `app.py` to layer loop | ✅      |
| B‑3 | Smoke‑test header‑only mapping  | ✅      |

### Phase C – Mapping Engine Generalisation

| #     | Task                                                  | Status | Done‑when                                     |
| ----- | ----------------------------------------------------- | ------ | --------------------------------------------- |
| C‑1   | Extract lookup embeddings to `lookup_layer.py`        | ✅      | PIT mapping skips embeddings for header‑only. |
| C‑1.2 | 🆕 Add confidence % display in lookup/header pages    | 🔜     | Suggestions show “92 % confident”.            |
| C‑1.3 | 🆕 GPT fallback for unmapped lookup values            | 🔜     | Button fills remaining blanks via GPT.        |
| C‑2   | Add computed layer `strategy: first_available` engine | ✅      | COA derives `NET_CHANGE`.                     |
| C‑2.1 | 🆕 Direct vs Computed toggle UI                       | 🚧     | Toggle appears in computed page.              |
| C‑2.2 | 🆕 Expression Builder component                       | 🚧     | User builds formula visually.                 |
| C‑2.3 | 🆕 Validate formula on sample rows                    | 🆕     | Preview shows calculated values or errors.    |
| C‑2.4 | 🆕 Store final expression & export                    | 🆕     | Mapping JSON includes user expression.        |
| C‑2.5 | 🆕 GPT propose expression helper                      | 🆕     | “Suggest formula” button visible.             |
| C‑3   | Unit tests for all layer strategies                   | ✅      | `pytest` suite green.                         |

### Phase D – Template Builder Wizard

| #   | Task                             | Status | Done‑when                |
| --- | -------------------------------- | ------ | ------------------------ |
| D‑1 | Column detector sidebar          | 🚧     | Columns auto‑listed.     |
| D‑2 | Mark required fields & save JSON | 🔜     | Saved, validator passes. |
| D‑3 | Create template from PIT inputs  | 🔜     | Opens in main app.       |

### Phase E – Repo Restructure & Docs (**complete**)

| #   | Task                           | Status |
| --- | ------------------------------ | ------ |
| E‑1 | Split `app_utils` sub‑packages | ✅      |
| E‑2 | Add `AGENTS.md` files          | ✅      |
| E‑3 | Remove TODO/FIXME              | ✅      |

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

## 4  Immediate Codex task list (updated)

```
### Context
Repo root = ai-mapping-agent (see /AGENTS.md for guidelines).

### Tasks
1. Implement confidence display in lookup & header pages (C‑1.2).
2. Build Expression Builder UI (C‑2.2) and direct/computed toggle (C‑2.1).
3. Add formula validation & storage (C‑2.3, C‑2.4).
4. Optional: GPT fallback and formula suggestion (C‑1.3, C‑2.5).
5. Implement Template Builder column detector (D‑1).
6. Save user‑flagged required columns to JSON (D‑2).
```
