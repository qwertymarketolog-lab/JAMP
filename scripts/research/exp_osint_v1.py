#!/usr/bin/env python3
import concurrent.futures, hashlib, json, os, re, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone

CATALOG="https://anymodel.org/v1/models"
CHAT="https://anymodel.org/v1/chat/completions"
TASK=("Determine whether Pluto is classified as a planet under the International "
      "Astronomical Union (IAU) 2006 definition. Return a concise answer, the "
      "decisive factual basis, and the URLs of the sources you relied on. "
      "Do not invent URLs. If you cannot retrieve or verify a source, say so.")
EXPECTED=86
TIMEOUT=45

def now(): return datetime.now(timezone.utc).isoformat()

def req(url, payload=None):
    h={"Accept":"application/json"}
    if payload is not None:
        h.update({"Content-Type":"application/json",
                  "Authorization":"Bearer "+os.environ["ANYMODEL_API_KEY"]})
    r=urllib.request.Request(url,
        data=None if payload is None else json.dumps(payload).encode(),
        headers=h, method="GET" if payload is None else "POST")
    t=time.monotonic()
    try:
        with urllib.request.urlopen(r, timeout=TIMEOUT) as x:
            return x.status,(time.monotonic()-t)*1000,x.read().decode("utf-8","replace"),None
    except Exception as e:
        body=""
        if isinstance(e, urllib.error.HTTPError):
            try: body=e.read().decode("utf-8","replace")
            except Exception: pass
        return getattr(e,"code",None),(time.monotonic()-t)*1000,body,repr(e)

def main():
    run=os.environ.get("GITHUB_RUN_ID","local")
    started=now()
    status,ms,catalog_raw,error=req(CATALOG)
    if error or status != 200:
        print(json.dumps({"experiment":"EXP-OSINT-V1","state":"HOLD","stage":"catalog",
                           "http_status":status,"error":error,"raw":catalog_raw},indent=2))
        return 2
    digest=hashlib.sha256(catalog_raw.encode()).hexdigest()
    try:
        obj=json.loads(catalog_raw)
        data=obj.get("data",obj) if isinstance(obj,dict) else obj
        cohort=sorted(x["id"] for x in data if isinstance(x,dict) and isinstance(x.get("id"),str)
                      and x["id"]!="am/free")
    except Exception as e:
        print(json.dumps({"experiment":"EXP-OSINT-V1","state":"HOLD","stage":"catalog_parse",
                           "error":repr(e)},indent=2))
        return 2
    if len(cohort)!=EXPECTED:
        print(json.dumps({"experiment":"EXP-OSINT-V1","state":"HOLD",
                          "reason":"COHORT_CARDINALITY_VIOLATION","expected":EXPECTED,
                          "observed":len(cohort),"excluded":["am/free"],
                          "catalog_sha256":digest,"catalog_raw":catalog_raw},indent=2))
        return 3
    cohort_sha=hashlib.sha256(json.dumps(cohort).encode()).hexdigest()
    print(f"COHORT_FROZEN n={len(cohort)} sha256={cohort_sha}",flush=True)

    def probe(model):
        payload={"model":model,"temperature":0,"max_tokens":500,
                 "messages":[{"role":"user","content":TASK}]}
        ts=now(); code,elapsed,raw,err=req(CHAT,payload); answer=""
        if raw:
            try: answer=json.loads(raw).get("choices",[{}])[0].get("message",{}).get("content","") or ""
            except Exception: pass
        return {"model":model,"observed_at":ts,"http_status":code,
                "elapsed_ms":round(elapsed,3),"raw_response":raw,"answer":answer,
                "urls_observed":re.findall(r'https?://[^\\s<>"\\]\)]+',answer),
                "error":err}
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        fs=[pool.submit(probe,m) for m in cohort]
        for f in concurrent.futures.as_completed(fs):
            x=f.result(); results.append(x)
            print(f"OBSERVED {x['model']} status={x['http_status']}",flush=True)
    results.sort(key=lambda x:x["model"])
    artifact={"experiment":"EXP-OSINT-V1","contract_version":"v1","state":"COMPLETED",
              "started_at":started,"finished_at":now(),
              "execution_id":"github-actions:"+run,"catalog_url":CATALOG,
              "catalog_sha256":digest,"cohort_n":86,"cohort":cohort,
              "cohort_sha256":cohort_sha,"chat_url":CHAT,"task":TASK,"results":results,
              "frozen_core":{"path":"src/jamp/run.py",
                             "expected_blob":"0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"}}
    path=f"artifacts/research/exp_osint_v1_{run}.json"
    os.makedirs(os.path.dirname(path),exist_ok=True)
    with open(path,"w",encoding="utf-8") as f: json.dump(artifact,f,ensure_ascii=False,indent=2)
    print("ARTIFACT="+path)
    return 0

if __name__=="__main__": sys.exit(main())
