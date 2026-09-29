#!/usr/bin/env python3
import json, os, sys, requests

URL = "https://anymodel.org/v1/chat/completions"
KEY = os.environ["ANYMODEL_API_KEY"]
MODELS = [
    "xai/grok-4.20-0309-non-reasoning",
    "xai/grok-4.20-0309-reasoning",
    "xai/grok-4.20-multi-agent-0309",
]
PROMPT = "Return exactly a short JSON object with keys identity_match, confidence, evidence_status, sources. If web access is unavailable, say so."

out=[]
for model in MODELS:
    rec={"model_requested":model}
    try:
        r=requests.post(URL,headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"},
            json={"model":model,"messages":[{"role":"user","content":PROMPT}],"temperature":0},timeout=60)
        rec["status_code"]=r.status_code
        rec["r_text"]=r.text
        try:
            data=r.json()
            rec["r_json_keys"]=sorted(data.keys()) if isinstance(data,dict) else None
            rec["id"]=data.get("id") if isinstance(data,dict) else None
            rec["model"]=data.get("model") if isinstance(data,dict) else None
        except Exception as e:
            rec["r_json_keys"]=None
            rec["id"]=None
            rec["model"]=None
            rec["json_decode_error"]=f"{type(e).__name__}: {e}"
    except Exception as e:
        rec["request_error"]=f"{type(e).__name__}: {e}"
    out.append(rec)

os.makedirs("artifacts/research",exist_ok=True)
json.dump({"experiment":"ANYMODEL-GROK420-CONTROLLED-PROBE","target_sha":"82583f055cd02bfbe3abff2b874739072497d080",
           "endpoint":URL,"results":out},open("artifacts/research/anymodel_grok420_controlled_probe.json","w",encoding="utf-8"),
          ensure_ascii=False,indent=2)
print("wrote artifacts/research/anymodel_grok420_controlled_probe.json")
