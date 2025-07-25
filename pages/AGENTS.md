# Streamlit Pages

* Each `.py` renders **one** page.
* Dynamic wizard steps live under `pages/steps/`.
* Import heavy logic from `app_utils.*` only (no business logic in pages).
* Keep per‑page state under keys prefixed with page name to avoid collisions.
