import os
import json
import streamlit as st
from app_utils.mapping_utils import load_progress
from app_utils.ui_utils import render_progress, compute_current_step


# Restore state and show progress
client_id = st.session_state.get("client_id", "default_client")
stored = load_progress(client_id)
for k, v in stored.items():
    if k not in st.session_state:
        st.session_state[k] = v
st.session_state["current_step"] = compute_current_step()
progress_container = st.sidebar.empty()
render_progress(progress_container)

st.title("Template Manager")

def validate_template_json(data: dict):
    if not isinstance(data, dict):
        return False, "Template must be a JSON object"
    required = ["template_name", "fields", "accounts"]
    for k in required:
        if k not in data:
            return False, f"Missing key '{k}'"
    if not isinstance(data.get("fields"), list) or not isinstance(data.get("accounts"), list):
        return False, "'fields' and 'accounts' must be lists"
    return True, ""

with st.sidebar:
    st.markdown("---")
    if st.button("Reset"):
        for k in [
            "header_suggestions",
            "header_confirmed",
            "account_suggestions",
            "account_confirmed",
        ]:
            st.session_state.pop(k, None)
        st.session_state["uploaded_file"] = None
        st.session_state["client_id"] = ""
        st.experimental_rerun()

    st.markdown("---")
    st.subheader("Template Manager")

    uploaded_template = st.file_uploader(
        "Upload Template JSON", type=["json"], key="template_upload")
    if uploaded_template is not None:
        try:
            data = json.load(uploaded_template)
            ok, msg = validate_template_json(data)
            if ok:
                safe_name = "".join(
                    c if c.isalnum() or c in "-_" else "_" for c in data["template_name"]
                )
                os.makedirs("templates", exist_ok=True)
                with open(os.path.join("templates", f"{safe_name}.json"), "w") as f:
                    json.dump(data, f, indent=2)
                st.success(f"Saved template '{safe_name}'")
                st.experimental_rerun()
            else:
                st.error(f"Invalid template: {msg}")
        except Exception as e:
            st.error(f"Failed to read JSON: {e}")

    with st.expander("Existing Templates", expanded=False):
        os.makedirs("templates", exist_ok=True)
        tmpl_files = [f for f in os.listdir("templates") if f.endswith(".json")]
        for tf in tmpl_files:
            c1, c2, c3 = st.columns([2, 1, 1])
            tmpl_name = tf[:-5]
            c1.write(tmpl_name)
            with open(os.path.join("templates", tf)) as f:
                c2.download_button(
                    "Download",
                    data=f.read(),
                    file_name=tf,
                    mime="application/json",
                    key=f"dl_{tf}"
                )
            if c3.button("Delete", key=f"del_{tf}"):
                os.remove(os.path.join("templates", tf))
                st.experimental_rerun()
