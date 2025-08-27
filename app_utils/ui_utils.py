"""
ui_utils.py  – Progress indicator & step utilities
--------------------------------------------------

• DEFAULT_STEPS always starts with “Upload File”.
• set_steps_from_template() builds the remaining steps
  dynamically from the *layers* array inside a template.
• compute_current_step() works for both legacy flags
  (header_confirmed / account_confirmed) and the new
  generic layer_confirmed_<n> flags.

Import signature (back-compat):
    from app_utils.ui_utils import render_progress, compute_current_step, STEPS
"""

from __future__ import annotations

import uuid
import streamlit as st
from contextlib import contextmanager
from typing import Iterator, List


def apply_global_css() -> None:
    st.markdown(
        """
        <style>
        :root { --gap: 10px; --card-pad: 14px; --card-radius: 10px; }

        /* Give the page some breathing room so the title isn't clipped */
        .block-container { padding-top: 36px; padding-bottom: 16px; }

        /* Tighter, consistent vertical rhythm everywhere */
        [data-testid="stVerticalBlock"] { gap: var(--gap) !important; }

        /* First H1 shouldn't crowd the header bar */
        .block-container h1:first-of-type { margin-top: 0; }

        /* Buttons that live together should look like they do */
        .button-row { display:flex; gap:8px; flex-wrap:wrap; }

        /* Card typography */
        .card-title { margin: 0 0 6px 0; font-weight: 600; font-size: 1.05rem; }
        .card-caption { margin: 0 0 8px 0; opacity: .85; font-size: 0.9rem; }

        /* Optional: narrower selects when you toggle a 'compact' class */
        .compact [data-testid="stSelectbox"] { max-width: 460px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


@contextmanager
def section_card(title: str, caption: str | None = None) -> Iterator[None]:
    """
    Render a titled, styled card. We place an invisible anchor inside a Streamlit
    container and then style *that container* with CSS using :has().
    """
    card = st.container()
    anchor_id = f"card_{uuid.uuid4().hex[:8]}"

    with card:
        st.markdown(f"<span id='{anchor_id}'></span>", unsafe_allow_html=True)
        st.markdown(f"<div class='card-title'>{title}</div>", unsafe_allow_html=True)
        if caption:
            st.markdown(f"<div class='card-caption'>{caption}</div>", unsafe_allow_html=True)

        yield  # all st.* calls from the caller render inside this container

        st.markdown(
            f"""
            <style>
            /* Style the container that *contains* our unique anchor */
            div[data-testid="stVerticalBlock"]:has(> span#{anchor_id}) {{
                border: 1px solid rgba(255,255,255,.10);
                border-radius: var(--card-radius);
                padding: var(--card-pad);
                background: rgba(255,255,255,.03);
                margin-bottom: 12px;
            }}
            /* Slightly tighter gaps for blocks nested inside this card */
            div[data-testid="stVerticalBlock"]:has(> span#{anchor_id}) [data-testid="stVerticalBlock"] {{
                gap: 8px !important;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# 1. Dynamic step handling
# ---------------------------------------------------------------------------

_DEFAULT_STEPS = ["Upload File"]  # first step is always the file upload
STEPS: List[str] = _DEFAULT_STEPS  # exported for legacy imports


def _layer_step_label(layer: dict, idx: int) -> str:
    """Return a human-friendly label for a template layer."""
    ltype = layer.get("type", "").lower()
    mapping = {
        "header": "Map Headers",
        "lookup": "Map Look-ups",
        "computed": "Confirm Computed Fields",
    }
    return mapping.get(ltype, f"Step {idx}: {ltype.capitalize()}")


def set_steps_from_template(layers: list[dict]) -> None:
    """
    Store the dynamic step list in st.session_state and expose it
    via the global STEPS symbol for any late imports.
    Call this right after the template is loaded.
    """
    global STEPS  # keep the legacy symbol in sync
    STEPS = _DEFAULT_STEPS + [
        _layer_step_label(layer, i + 1) for i, layer in enumerate(layers)
    ]
    st.session_state["steps"] = STEPS


def get_steps() -> List[str]:
    """Return the current step list (dynamic if already built)."""
    return st.session_state.get("steps", STEPS)


# ---------------------------------------------------------------------------
# 2. Progress utilities
# ---------------------------------------------------------------------------


def compute_current_step() -> int:
    """
    Determine which step the user is on (1-based index in STEPS).

    Logic:
    • 0  – nothing uploaded
    • 1  – file uploaded
    • +n – for each confirmed layer (layer_confirmed_<idx>)
    • Legacy fallback: header_confirmed / account_confirmed
    """
    if st.session_state.get("uploaded_file") is None:
        return 0  # still on Start

    # base index: upload done
    idx = 1

    # generic layer confirmations
    confirmed_dynamic = [
        k for k, v in st.session_state.items() if k.startswith("layer_confirmed_") and v
    ]
    idx += len(confirmed_dynamic)

    # legacy flags (will disappear once Home.py is refactored)
    if (
        st.session_state.get("header_confirmed")
        and "layer_confirmed_0" not in st.session_state
    ):
        idx += 1
    if (
        st.session_state.get("account_confirmed")
        and "layer_confirmed_1" not in st.session_state
    ):
        idx += 1

    return idx


def _jump_to_step(step_idx: int) -> None:
    """Set current step and rerun the app."""
    st.session_state["current_step"] = step_idx
    st.rerun()


def render_progress(container: st.delta_generator.DeltaGenerator | None = None) -> None:
    """
    Render a persistent sidebar progress indicator.
    """
    steps = get_steps()
    current = st.session_state.get("current_step", 0)
    styles = """
    <style>
    .progress-list{position:relative;margin-left:20px;}
    .progress-list::before{content:"";position:absolute;left:-8px;top:0;bottom:0;width:4px;background:#ccc;}
    .step{position:relative;padding-left:12px;margin-bottom:0.5rem;}
    .step.completed{color:#000;}
    .step.current{font-weight:bold;color:#000;background:rgba(0,128,0,0.1);border-radius:4px;}
    .step.todo{color:#999;}
    .step::before{content:"";position:absolute;left:-12px;top:4px;width:8px;height:8px;border-radius:50%;background:#ccc;}
    .step.completed::before{background:#28a745;}
    .step.current::before{background:#28a745;animation:pulse 2s infinite;}
    .progress-list div[data-testid="stButton"]{position:relative;padding-left:12px;margin-bottom:0.5rem;}
    .progress-list div[data-testid="stButton"]::before{content:"";position:absolute;left:-12px;top:4px;width:8px;height:8px;border-radius:50%;background:#28a745;}
    .progress-list div[data-testid="stButton"]>button{color:#000;background:none;border:none;padding:0;text-align:left;}
    @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(40,167,69,0.7);}70%{box-shadow:0 0 0 8px rgba(40,167,69,0);}100%{box-shadow:0 0 0 0 rgba(40,167,69,0);}}
    </style>
    """
    target = container if container is not None else st.sidebar
    with target:
        st.markdown(styles, unsafe_allow_html=True)
        st.subheader("Progress")
        st.markdown('<div class="progress-list">', unsafe_allow_html=True)
        for i, step in enumerate(steps, start=1):
            if current > i:
                if st.button(step, key=f"step_{i}"):
                    _jump_to_step(i)
            elif current == i:
                st.markdown(
                    f'<div class="step current">{step}</div>', unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f'<div class="step todo">{step}</div>', unsafe_allow_html=True
                )
        st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# 3. Field label helpers
# ---------------------------------------------------------------------------


def render_required_label(text: str) -> None:
    """Render a field label with a red asterisk."""
    st.markdown(f"{text} <span style='color:red'>*</span>", unsafe_allow_html=True)
