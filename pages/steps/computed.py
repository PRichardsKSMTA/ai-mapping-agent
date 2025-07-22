import streamlit as st

def render(layer, idx: int):
    st.header("Computed Field Confirmation")
    st.json(layer.model_dump())  # temporary display
    if st.button("Confirm", key=f"confirm_{idx}"):
        st.session_state[f"layer_confirmed_{idx}"] = True
        st.rerun()
