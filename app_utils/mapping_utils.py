import os
import json
import numpy as np
from datetime import datetime
import streamlit as st
from openai import OpenAI

from app_utils.mapping.lookup_layer import suggest_lookup_mapping
from difflib import get_close_matches, SequenceMatcher

# Initialize OpenAI client using Streamlit's secrets
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Memory helpers

def get_memory_path(client_id, template_name, map_type):
    os.makedirs("memories", exist_ok=True)
    return os.path.join("memories", f"{client_id}_{template_name}_{map_type}.jsonl")

def load_header_corrections(client_id, template_name):
    try:
        return [json.loads(line) for line in open(get_memory_path(client_id, template_name, "header"))]
    except FileNotFoundError:
        return []

def save_header_corrections(client_id, template_name, corrections):
    path = get_memory_path(client_id, template_name, "header")
    with open(path, "a") as f:
        for c in corrections:
            f.write(json.dumps(c) + "\n")

def load_account_corrections(client_id, template_name):
    try:
        return [json.loads(line) for line in open(get_memory_path(client_id, template_name, "account"))]
    except FileNotFoundError:
        return []

def save_account_corrections(client_id, template_name, corrections):
    path = get_memory_path(client_id, template_name, "account")
    with open(path, "a") as f:
        for c in corrections:
            f.write(json.dumps(c) + "\n")

# Progress persistence helpers

def get_progress_path(client_id):
    os.makedirs("memories", exist_ok=True)
    return os.path.join("memories", f"{client_id}_progress.json")

def load_progress(client_id):
    try:
        with open(get_progress_path(client_id)) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_progress(client_id, step_key, value=True):
    path = get_progress_path(client_id)
    data = load_progress(client_id)
    data[step_key] = value
    with open(path, "w") as f:
        json.dump(data, f)

# Template loader & mapping functions

def load_template(name: str):
    path = os.path.join("templates", f"{name}.json")
    with open(path) as f:
        return json.load(f)

def suggest_mapping(template: dict, sample_data: list, prior_mappings: list = []):
    system = (
        "You are a data-mapping assistant.\n"
        "Given a target template and sample data (JSON),\n"
        "output a JSON array of {template_field, client_column, reasoning, confidence (0–100)}.\n"
        "Use prior corrections to improve accuracy."
    )
    payload = {"template": template, "sample_data": sample_data, "prior_mappings": prior_mappings}
    resp = client.chat.completions.create(model="gpt-4.1-nano", messages=[
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload)}
    ], temperature=0.2)
    return json.loads(resp.choices[0].message.content)

def cosine_similarity(a, b):
    a_arr, b_arr = np.array(a), np.array(b)
    return float(a_arr.dot(b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))

@st.cache_data(show_spinner=False)
def compute_template_embeddings(template_accounts: list, model: str = "text-embedding-ada-002"):
    out = []
    for acc in template_accounts:
        resp = client.embeddings.create(model=model, input=acc["GL_NAME"])
        out.append({
            "GL_NAME": acc["GL_NAME"],
            "GL_ID": acc["GL_ID"],
            "embedding": resp.data[0].embedding
        })
    return out

def match_account_names(
    sample_records: list,
    template_embeddings: list,
    prior_account_corrections: list = None,
    threshold: float = 0.7,
    model: str = "text-embedding-ada-002"
):
    prior_map = {c["client_GL_NAME"]: c for c in (prior_account_corrections or [])}
    matches = []
    for rec in sample_records:
        name = rec.get("GL_NAME", "")
        if name in prior_map:
            pc = prior_map[name]
            matches.append({
                "client_GL_NAME": name,
                "matched_GL_NAME": pc["matched_GL_NAME"],
                "GL_ID": pc["GL_ID"],
                "confidence": 100,
                "reasoning": "User correction"
            })
            continue
        resp = client.embeddings.create(model=model, input=name)
        emb = resp.data[0].embedding
        best_score, best_acc = max(
            ((cosine_similarity(emb, te["embedding"]), te) for te in template_embeddings),
            key=lambda x: x[0]
        )
        pct = int(round(best_score * 100))
        if best_score >= threshold:
            reasoning = f"Similarity {pct}% to '{best_acc['GL_NAME']}'"
            matches.append({
                "client_GL_NAME": name,
                "matched_GL_NAME": best_acc["GL_NAME"],
                "GL_ID": best_acc["GL_ID"],
                "confidence": pct,
                "reasoning": reasoning
            })
        else:
            matches.append({
                "client_GL_NAME": name,
                "matched_GL_NAME": None,
                "GL_ID": None,
                "confidence": pct,
                "reasoning": f"No match ≥ {int(threshold * 100)}%"
            })
    return matches

def match_lookup_values(source_series, dictionary_list):
    """Legacy wrapper used by pages.steps.lookup."""
    return suggest_lookup_mapping(list(source_series), list(dictionary_list))

def suggest_header_mapping(template_fields: list[str], source_columns: list[str]):
    """Return fuzzy header suggestions with confidence scores."""

    out: dict[str, dict[str, float]] = {}
    lower_map = {c.lower(): c for c in source_columns}
    lower_list = list(lower_map.keys())

    for tf in template_fields:
        matches = get_close_matches(tf.lower(), lower_list, n=1, cutoff=0)
        if matches:
            best_lower = matches[0]
            best_src = lower_map[best_lower]
            ratio = SequenceMatcher(None, tf.lower(), best_lower).ratio()
            if ratio >= 0.5:
                out[tf] = {"src": best_src, "confidence": ratio}
                continue
        out[tf] = {}

    return out
