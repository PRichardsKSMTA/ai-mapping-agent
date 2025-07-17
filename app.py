import os
from datetime import datetime
from dotenv import load_dotenv
import streamlit as st
import pandas as pd

from utils.excel_utils import excel_to_json
from utils.mapping_utils import (
    load_template,
    suggest_mapping,
    compute_template_embeddings,
    match_account_names,
    load_header_corrections,
    save_header_corrections,
    load_account_corrections,
    save_account_corrections,
)

# Load environment
load_dotenv()

# Streamlit config
st.set_page_config(page_title="AI Mapping Agent", layout="wide")
st.title("AI Mapping Agent 🗺️")
st.write("Upload client data (left) and map to your destination template (right).")

# Client ID
client_id = st.text_input("Client ID", value="default_client")

# Debug info
st.write("📂 CWD:", os.getcwd())
try:
    st.write("📄 templates/:", os.listdir("templates"))
except Exception:
    pass

# File upload
uploaded = st.file_uploader("Upload Excel file", type=["xls","xlsx","xlsm"])
if not uploaded:
    st.stop()

# Parse file
records, columns = excel_to_json(uploaded)
st.subheader("Detected Columns")
st.write(columns)
st.subheader("Sample Record")
st.json(records[0])

# Template selection
st.subheader("Step 1: Select Template & Map Headers")
templates = [f[:-5] for f in os.listdir("templates") if f.endswith(".json")]
tmpl_name = st.selectbox("Template", templates)

if tmpl_name:
    template = load_template(tmpl_name)

    # Header mapping suggestions
    if "header_suggestions" not in st.session_state:
        if st.button("Suggest Header Mappings"):
            with st.spinner("Generating header mapping suggestions…"):
                prior = load_header_corrections(client_id, tmpl_name)
                st.session_state["header_suggestions"] = suggest_mapping(
                    template, records[:5], prior
                )

    # Show and edit header mappings
    if "header_suggestions" in st.session_state:
        hdr = st.session_state["header_suggestions"]
        df_hdr = pd.DataFrame(hdr)
        df_hdr["confidence"] = df_hdr["confidence"].astype(str) + " %"
        # Reorder: Client → Template → Confidence → Reasoning
        df_hdr = df_hdr[["client_column", "template_field", "confidence", "reasoning"]]

        st.subheader("Header Mapping")
        edited = st.data_editor(
            df_hdr,
            column_config={
                # client_column as dropdown
                "client_column": st.column_config.SelectboxColumn(
                    label="Client Column",
                    options=columns,
                    help="Select the correct client column"
                ),
                # template_field read-only
                "template_field": st.column_config.TextColumn(
                    label="Template Field", disabled=True
                ),
                # confidence read-only
                "confidence": st.column_config.TextColumn(
                    label="Confidence", disabled=True
                ),
                # reasoning read-only
                "reasoning": st.column_config.TextColumn(
                    label="Reasoning", disabled=True
                ),
            },
            hide_index=True,
            use_container_width=True
        )
        if st.button("Confirm Header Mappings"):
            corrections = []
            for orig, row in zip(hdr, edited.to_dict("records")):
                if orig["client_column"] != row["client_column"]:
                    corrections.append({
                        "template_field": orig["template_field"],
                        "correct_client_column": row["client_column"],
                        "timestamp": datetime.utcnow().isoformat()
                    })
            if corrections:
                save_header_corrections(client_id, tmpl_name, corrections)
            st.session_state["header_confirmed"] = True
            st.success("✅ Header mappings confirmed")

    # Display final header mappings
    if st.session_state.get("header_confirmed"):
        st.subheader("Final Header Mappings")
        final_hdr = pd.DataFrame(st.session_state["header_suggestions"])
        final_hdr["confidence"] = final_hdr["confidence"].astype(str) + " %"
        final_hdr = final_hdr[["client_column", "template_field", "confidence"]]
        st.table(final_hdr)

        # Step 2: Account mapping
        st.subheader("Step 2: Match Account Names to Standard COA")
        if "account_suggestions" not in st.session_state:
            if st.button("Suggest Account Name Mappings"):
                with st.spinner("Matching account names…"):
                    if "tmpl_acc_emb" not in st.session_state:
                        st.session_state["tmpl_acc_emb"] = compute_template_embeddings(
                            template["accounts"]
                        )
                    prior = load_account_corrections(client_id, tmpl_name)
                    st.session_state["account_suggestions"] = match_account_names(
                        records,
                        st.session_state["tmpl_acc_emb"],
                        prior
                    )

        # Show and edit account mappings
        if "account_suggestions" in st.session_state:
            acc = st.session_state["account_suggestions"]
            df_acc = pd.DataFrame(acc)
            df_acc["confidence"] = df_acc["confidence"].astype(str) + " %"
            std_names = [a["GL_NAME"] for a in template["accounts"]]
            df_acc = df_acc[["client_GL_NAME", "matched_GL_NAME", "confidence", "reasoning"]]

            st.subheader("Account Name Mapping")
            edited2 = st.data_editor(
                df_acc,
                column_config={
                    "client_GL_NAME": st.column_config.TextColumn(
                        label="Client GL Name", disabled=True
                    ),
                    "matched_GL_NAME": st.column_config.SelectboxColumn(
                        label="Matched COA Name",
                        options=std_names,
                        help="Select the matching COA name"
                    ),
                    "confidence": st.column_config.TextColumn(
                        label="Confidence", disabled=True
                    ),
                    "reasoning": st.column_config.TextColumn(
                        label="Reasoning", disabled=True
                    ),
                },
                hide_index=True,
                use_container_width=True
            )
            if st.button("Confirm Account Mappings"):
                corrections = []
                for orig, row in zip(acc, edited2.to_dict("records")):
                    if orig["matched_GL_NAME"] != row["matched_GL_NAME"]:
                        corrections.append({
                            "client_GL_NAME": orig["client_GL_NAME"],
                            "matched_GL_NAME": row["matched_GL_NAME"],
                            "timestamp": datetime.utcnow().isoformat()
                        })
                if corrections:
                    save_account_corrections(client_id, tmpl_name, corrections)
                st.success("✅ Account mappings confirmed")