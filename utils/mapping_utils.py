import os
import json
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

# Load env & init client
load_dotenv()
client = OpenAI()

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
        {"role":"system","content":system},
        {"role":"user","content":json.dumps(payload)}
    ], temperature=0.2)
    return json.loads(resp.choices[0].message.content)

def cosine_similarity(a,b):
    a_arr, b_arr = np.array(a), np.array(b)
    return float(a_arr.dot(b_arr)/(np.linalg.norm(a_arr)*np.linalg.norm(b_arr)))

def compute_template_embeddings(template_accounts: list, model: str = "text-embedding-ada-002"):
    out = []
    for acc in template_accounts:
        resp = client.embeddings.create(model=model, input=acc["GL_NAME"])
        out.append({"GL_NAME":acc["GL_NAME"],"GL_ID":acc["GL_ID"],"embedding":resp.data[0].embedding})
    return out

def match_account_names(sample_records: list, template_embeddings: list, prior_account_corrections: list = None, threshold: float = 0.7, model: str = "text-embedding-ada-002"):
    prior_map = {c["client_GL_NAME"]:c for c in (prior_account_corrections or [])}
    matches = []
    for rec in sample_records:
        name = rec.get("GL_NAME","")
        if name in prior_map:
            pc = prior_map[name]
            matches.append({"client_GL_NAME":name, "matched_GL_NAME":pc["matched_GL_NAME"], "GL_ID":pc["GL_ID"], "confidence":100, "reasoning":"User correction"})
            continue
        resp = client.embeddings.create(model=model, input=name)
        emb = resp.data[0].embedding
        best_score, best_acc = max(((cosine_similarity(emb,te["embedding"]), te) for te in template_embeddings), key=lambda x:x[0])
        pct = int(round(best_score*100))
        if best_score >= threshold:
            reasoning = f"Similarity {pct}% to '{best_acc['GL_NAME']}'"
            matches.append({"client_GL_NAME":name, "matched_GL_NAME":best_acc["GL_NAME"], "GL_ID":best_acc["GL_ID"], "confidence":pct, "reasoning":reasoning})
        else:
            matches.append({"client_GL_NAME":name, "matched_GL_NAME":None, "GL_ID":None, "confidence":pct, "reasoning":f"No match ≥ {int(threshold*100)}%"})
    return matches
