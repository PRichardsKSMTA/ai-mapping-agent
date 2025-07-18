import streamlit as st

# Steps used across the application
STEPS = ["Upload File", "Map Headers", "Match Account Names"]

def compute_current_step() -> int:
    """Determine which step the user is currently on."""
    if st.session_state.get("account_confirmed"):
        return 3
    if st.session_state.get("header_confirmed"):
        return 2
    if st.session_state.get("uploaded_file") is not None:
        return 1
    return 0


def render_progress(container: st.delta_generator.DeltaGenerator | None = None):
    """Render a persistent sidebar progress indicator."""
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
    @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(40,167,69,0.7);}70%{box-shadow:0 0 0 8px rgba(40,167,69,0);}100%{box-shadow:0 0 0 0 rgba(40,167,69,0);}}
    </style>
    """
    target = container if container is not None else st.sidebar
    with target:
        st.markdown(styles, unsafe_allow_html=True)
        st.subheader("Progress")
        st.markdown('<div class="progress-list">', unsafe_allow_html=True)
        for i, step in enumerate(STEPS, start=1):
            if current > i:
                cls = "completed"
            elif current == i:
                cls = "current"
            else:
                cls = "todo"
            st.markdown(f'<div class="step {cls}">{step}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
