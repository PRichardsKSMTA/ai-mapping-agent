import os
from datetime import datetime
import json
import streamlit as st
import pandas as pd

# Expose API key from Streamlit secrets for OpenAI
if "OPENAI_API_KEY" in st.secrets:
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]

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
from utils.ui_utils import render_progress, STEPS

# Streamlit config
st.set_page_config(page_title="AI Mapping Agent", layout="wide")
st.title("AI Mapping Agent 🗺️")


# Overview instructions
with st.expander("Help", expanded=True):
    st.markdown(
        """
        **Welcome!** Use this tool in two steps:
        - **Header Mapping** – match your columns to the template.
        - **Account Mapping** – map GL names to the standard COA.
        - Use **Override?** to change a suggestion and press **Confirm**.
        """
    )

# Client ID
client_id = st.text_input(
    "Client ID",
    value="default_client",
    key="client_id",
    help="Used to store and reload your corrections",
)
st.caption(
    "Changing the Client ID loads any saved header or account corrections for that ID."
)

# Debug info (for admins)
# st.write("📂 Current working directory:", os.getcwd())
try:
    # st.write("📄 Available templates:", os.listdir("templates"))  # Uncomment for debugging
    pass
except Exception:
    pass

# Step progress indicator
if "current_step" not in st.session_state:
    st.session_state["current_step"] = 0

render_progress()

# File upload
st.header("1. Upload Client File")
uploaded = st.file_uploader("Choose an Excel file", type=["xls","xlsx","xlsm"])
if uploaded:
    st.session_state["current_step"] = 1
else:
    st.stop()

# Parse file and preview
try:
    records, columns = excel_to_json(uploaded)
except Exception as e:
    st.error(f"Failed to parse the uploaded file: {e}")
    st.stop()

st.subheader("Preview: Detected Columns")
st.write(columns)
st.subheader("Preview: First Few Rows")
st.dataframe(pd.DataFrame(records).head())

# Template selection
st.header("2. Select Template & Map Headers")
templates = [f[:-5] for f in os.listdir("templates") if f.endswith(".json")]
tmpl_name = st.selectbox("Choose a template", templates)

if tmpl_name:
    template = load_template(tmpl_name)

    # Suggest header mappings
    if "header_suggestions" not in st.session_state:
        if st.button("Suggest Header Mappings"):
            with st.spinner("AI is generating header mappings…"):
                prior = load_header_corrections(client_id, tmpl_name)
                st.session_state["header_suggestions"] = suggest_mapping(
                    template, records[:5], prior
                )

    # Header mapping editing
    if "header_suggestions" in st.session_state:
        st.info(
            "**Instructions:** Check 'Override?' for any row you want to change, then use the 'Client Column' dropdown to select the correct column."
        )
        hdr = st.session_state["header_suggestions"]
        df_hdr = pd.DataFrame(hdr)
        df_hdr["confidence"] = df_hdr["confidence"].astype(str) + " %"
        df_hdr["override"] = False
        df_hdr = df_hdr[["override", "client_column", "template_field", "confidence", "reasoning"]]

        edited = st.data_editor(
            df_hdr,
            column_config={
                "client_column": st.column_config.SelectboxColumn(
                    label="Client Column", options=columns
                ),
                "template_field": st.column_config.TextColumn(label="Template Field", disabled=True),
                "confidence": st.column_config.TextColumn(label="Confidence", disabled=True),
                "reasoning": st.column_config.TextColumn(label="Reasoning", disabled=True),
            },
            hide_index=True,
            use_container_width=True
        )
        if st.button("Confirm Header Mappings"):
            corrections = []
            updated = []
            for orig, row in zip(hdr, edited.to_dict("records")):
                if row.get("override"):
                    new_col = row["client_column"]
                    if orig["client_column"] != new_col:
                        corrections.append({
                            "template_field": orig["template_field"],
                            "correct_client_column": new_col,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    orig["client_column"] = new_col
                updated.append(orig)
            if corrections:
                save_header_corrections(client_id, tmpl_name, corrections)
            st.session_state["header_suggestions"] = updated
            st.session_state["header_confirmed"] = True
            st.session_state["current_step"] = 2
            st.success("✅ Header mappings confirmed")

    # Final header mappings view
    if st.session_state.get("header_confirmed"):
        st.subheader("Final Header Mappings")
        final_hdr = pd.DataFrame(st.session_state["header_suggestions"])
        final_hdr["confidence"] = final_hdr["confidence"].astype(str) + " %"
        final_hdr = final_hdr[["client_column", "template_field", "confidence"]]
        st.table(final_hdr)

        # Account name mapping step
        st.header("3. Match Account Names to Standard COA")
        if "account_suggestions" not in st.session_state:
            if st.button("Suggest Account Name Mappings"):
                with st.spinner("AI is matching account names…"):
                    prior = load_account_corrections(client_id, tmpl_name)
                    tmpl_acc_emb = compute_template_embeddings(template["accounts"])
                    st.session_state["account_suggestions"] = match_account_names(
                        records,
                        tmpl_acc_emb,
                        prior
                    )

        if "account_suggestions" in st.session_state:
            st.info(
                "**Instructions:** Check 'Override?' for any account you want to change, then use the 'Matched COA Name' dropdown."
            )
            acc = st.session_state["account_suggestions"]
            df_acc = pd.DataFrame(acc)
            df_acc["confidence"] = df_acc["confidence"].astype(str) + " %"
            df_acc["override"] = False
            std_names = [a["GL_NAME"] for a in template["accounts"]]
            df_acc = df_acc[["override", "client_GL_NAME", "matched_GL_NAME", "confidence", "reasoning"]]

            edited2 = st.data_editor(
                df_acc,
                column_config={
                    "client_GL_NAME": st.column_config.TextColumn(label="Client GL Name", disabled=True),
                    "matched_GL_NAME": st.column_config.SelectboxColumn(
                        label="Matched COA Name", options=std_names
                    ),
                    "confidence": st.column_config.TextColumn(label="Confidence", disabled=True),
                    "reasoning": st.column_config.TextColumn(label="Reasoning", disabled=True),
                },
                hide_index=True,
                use_container_width=True
            )
            if st.button("Confirm Account Mappings"):
                corrections = []
                updated_acc = []
                for orig, row in zip(acc, edited2.to_dict("records")):
                    if row.get("override"):
                        new_match = row["matched_GL_NAME"]
                        if orig["matched_GL_NAME"] != new_match:
                            corrections.append({
                                "client_GL_NAME": orig["client_GL_NAME"],
                                "matched_GL_NAME": new_match,
                                "timestamp": datetime.utcnow().isoformat()
                            })
                        orig["matched_GL_NAME"] = new_match
                    updated_acc.append(orig)
                if corrections:
                    save_account_corrections(client_id, tmpl_name, corrections)
                st.session_state["account_suggestions"] = updated_acc
                st.session_state["current_step"] = 3
                st.success("✅ Account mappings confirmed")

                # Aggregate confirmed mappings
                header_map = [
                    {
                        "client_column": h["client_column"],
                        "template_field": h["template_field"],
                    }
                    for h in st.session_state.get("header_suggestions", [])
                ]
                account_map = [
                    {
                        "client_GL_NAME": a["client_GL_NAME"],
                        "matched_GL_NAME": a["matched_GL_NAME"],
                    }
                    for a in st.session_state.get("account_suggestions", [])
                ]
                aggregated = {"headers": header_map, "accounts": account_map}

                fmt = st.selectbox("Download format", ["CSV", "JSON"])
                if fmt == "CSV":
                    header_df = pd.DataFrame(header_map)
                    header_df["mapping_type"] = "header"
                    header_df.rename(
                        columns={"client_column": "source", "template_field": "target"},
                        inplace=True,
                    )
                    account_df = pd.DataFrame(account_map)
                    account_df["mapping_type"] = "account"
                    account_df.rename(
                        columns={"client_GL_NAME": "source", "matched_GL_NAME": "target"},
                        inplace=True,
                    )
                    csv_data = (
                        pd.concat([header_df, account_df], ignore_index=True)[
                            ["mapping_type", "source", "target"]
                        ].to_csv(index=False)
                    )
                    st.download_button(
                        "Download Mappings",
                        data=csv_data,
                        file_name="mappings.csv",
                        mime="text/csv",
                    )
                else:
                    json_data = json.dumps(aggregated, indent=2)
                    st.download_button(
                        "Download Mappings",
                        data=json_data,
                        file_name="mappings.json",
                        mime="application/json",
                    )
