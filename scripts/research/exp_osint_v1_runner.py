#!/usr/bin/env python3
import json, os, re, sys, time, uuid
from datetime import datetime, timezone
import requests

CHAT_URL="https://anymodel.org/v1/chat/completions"
KEY=os.environ["ANYMODEL_API_KEY"]
MODELS=json.load(open("config/exp_osint_v1_86_models.json"))["models"]
SHARD=int(os.getenv("SHARD","0")); SHARDS=int(os.getenv("SHARDS","12"))
QUERY="Вискунов Эдуард Леонидович"
PROMPT=f"""Найди в открытом интернете публичную профессиональную/проектную информацию о человеке по запросу: {QUERY}.
Цель: проверить, встречаются ли публичные связи с JAMP, GitHub repository qwertymarketolog-lab/JAMP, GitHub account qwertymarketolog-lab или alias ELVis.
Отделяй подтверждённые совпадения от возможных однофамильцев. Не собирай и не публикуй адреса, телефоны, документы, пароли, финансовые, медицинские или семейные сведения.
Верни JSON с полями answer_summary, sources (URL), entities, identity_match (confirmed|possible|not_found|uncertain), confidence (0..1), evidence_status. Если веб-доступа нет, честно укажи это."""
out=[]
for i,model in enumerate(MODELS):
    if i % SHARDS != SHARD: continue
    eid=str(uuid.uuid4()); t=datetime.now(timezone.utc).isoformat()
    rec={"model":model,"execution_id":eid,"execution_id_type":"client_uuid","query":QUERY,"timestamp":t}
    try:
        r=requests.post(CHAT_URL,headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"},
          json={"model":model,"messages":[{"role":"user","content":PROMPT}],"temperature":0},timeout=60)
        rec["http_status"]=r.status_code
        data=r.json(); text=data["choices"][0]["message"]["content"]
        rec["answer"]=text
        rec["sources"]=sorted(set(re.findall(r'https?://[^\\s\\]<>"\\)]+',text)))
        rec["request_id"]=data.get("id")
        rec["provider_model"]=data.get("model")
        try:
            obj=json.loads(text); rec["parsed"]=obj
        except Exception: rec["parsed"]=None
        rec["evidence_status"]="OBSERVED" if r.ok else "ERROR"
    except Exception as e:
        rec["error"]=f"{type(e).__name__}: {e}"; rec["evidence_status"]="ERROR"
    out.append(rec)
    time.sleep(0.2)
os.makedirs("artifacts/research",exist_ok=True)
path=f"artifacts/research/exp_osint_v1_raw_shard_{SHARD:02d}.json"
json.dump({"experiment":"EXP-OSINT-V1","cohort":"EXP-OSINT-V1-86","shard":SHARD,"shards":SHARDS,"results":out},open(path,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
print(path)
