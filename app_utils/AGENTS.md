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
