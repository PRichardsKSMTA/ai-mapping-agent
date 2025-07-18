import streamlit as st

# Steps used across the application
STEPS = ["Upload File", "Map Headers", "Match Account Names"]


def render_progress():
    """Render a persistent sidebar progress indicator."""
    current = st.session_state.get("current_step", 0)
    with st.sidebar:
        st.subheader("Progress")
        st.progress(current / len(STEPS))
        for i, step in enumerate(STEPS, start=1):
            if current > i:
                status = "Completed"
            elif current == i:
                status = "In Progress"
            else:
                status = "Not Started"
            st.write(f"**{step}** - {status}")
