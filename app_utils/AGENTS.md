# app_utils – Guidelines

| Sub‑module | Responsibility |
|------------|----------------|
| ai/                | OpenAI helpers (embeddings, GPT). |
| mapping/           | Core layer‑wise mapping algorithms and exporter. |
| ui/                | Streamlit widgets / dialogs. |
| excel_utils.py     | Reading/writing Excel & CSV. Pure functions. |
| suggestion_store.py| Persist per-field mapping suggestions. |

Don’ts
* Never import Streamlit outside `ui/` modules.
* Never store large DataFrames in `st.session_state`; keep only primitives/metadata.
