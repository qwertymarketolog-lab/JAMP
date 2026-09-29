#!/usr/bin/env python3
"""Deterministic R27 evaluation harness implementing PR-EVAL-PARAM-v1 and Contract v1.1."""
from __future__ import annotations
import argparse, hashlib, json, re, time
from pathlib import Path
from typing import Any

PARAM_ACCEPTED="PARAM_ACCEPTED"; PARAM_TRUNCATED="PARAM_TRUNCATED"; PARAM_REJECTED="PARAM_REJECTED"; PARAM_UNRESOLVED="PARAM_UNRESOLVED"
QUALIFIED="QUALIFIED"; FAILED="FAILED"; INCONCLUSIVE="INCONCLUSIVE"; CONTRACT_VIOLATION="CONTRACT_VIOLATION"
R28_CANDIDATE="R28_CANDIDATE"; HOLD="HOLD"
FROZEN_PARAMS={"temperature":0.0,"top_p":1.0,"max_tokens":256,"stream":False}
TIMEOUT_S=30.0; EXPECTED_R27_MODELS=17

VECTORS={
"E01":"Reply with exactly: JAMP-E01-OK",
"E02":'Return exactly this JSON object and no other text:\n{"jamp_e02":"OK","value":17}',
"E03":"Calculate exactly: (137 * 29) - 411.\nReply with only the integer.",
"E04":"What is the chemical symbol for gold?\nReply with only the chemical symbol.",
"E05":"Remember this identifier exactly: JAMP-E05-7C91.\nNow reply with only that identifier.",
"E06":"Reply with exactly this string and nothing else:\nJAMP-E06-ÄΩЖ中🚀",
"E07":"Reply with exactly one line in this format:\nJAMP-E07:<integer>\nUse the integer 42.",
}

def sha256_text(value:str)->str:
    return "sha256:"+hashlib.sha256(value.encode("utf-8")).hexdigest()

def parameter_resolution(response:Any,http_status:int|None)->tuple[str,dict[str,Any]]:
    d={"output_budget_status":PARAM_UNRESOLVED,"raw_finish_reason":None,"http_status_code":http_status,
       "prompt_tokens":None,"completion_tokens":None,"reasoning_tokens":None}
    if http_status is None or http_status>=500 or http_status in {401,403,404,408,409,422,429}: return PARAM_UNRESOLVED,d
    if http_status==400:
        err=response.get("error",{}) if isinstance(response,dict) else {}
        text=json.dumps(err,ensure_ascii=False).lower()
        explicit=str(err.get("param","")).lower()=="max_tokens" or str(err.get("parameter","")).lower()=="max_tokens"
        explicit=explicit or ("max_tokens" in text and any(w in text for w in ("invalid","unsupported","reject")))
        return (PARAM_REJECTED if explicit else PARAM_UNRESOLVED), d|{"parameter_error":err}
    if http_status!=200 or not isinstance(response,dict): return PARAM_UNRESOLVED,d
    choices=response.get("choices")
    if not isinstance(choices,list) or not choices or not isinstance(choices[0],dict): return PARAM_UNRESOLVED,d
    reason=choices[0].get("finish_reason"); d["raw_finish_reason"]=reason
    usage=response.get("usage") if isinstance(response.get("usage"),dict) else {}
    d["prompt_tokens"]=usage.get("prompt_tokens"); d["completion_tokens"]=usage.get("completion_tokens")
    details=usage.get("completion_tokens_details")
    if isinstance(details,dict): d["reasoning_tokens"]=details.get("reasoning_tokens")
    if reason=="stop": return PARAM_ACCEPTED,d
    if reason=="length": return PARAM_TRUNCATED,d
    return PARAM_UNRESOLVED,d

def response_content(response:Any)->str|None:
    if not isinstance(response,dict) or not isinstance(response.get("choices"),list) or not response["choices"]: return None
    first=response["choices"][0]
    if not isinstance(first,dict): return None
    msg=first.get("message")
    if isinstance(msg,dict) and isinstance(msg.get("content"),str): return msg["content"]
    if isinstance(first.get("text"),str): return first["text"]
    return None

def check(test_id:str,out:str)->str:
    expected={"E01":"JAMP-E01-OK","E03":"3562","E04":"Au","E05":"JAMP-E05-7C91","E06":"JAMP-E06-ÄΩЖ中🚀"}
    if test_id in expected: return "PASS" if out==expected[test_id] else "FAIL"
    if test_id=="E02":
        try: return "PASS" if json.loads(out)=={"jamp_e02":"OK","value":17} else "FAIL"
        except (TypeError,ValueError): return "FAIL"
    return "PASS" if re.fullmatch(r"JAMP-E07:42",out) else "FAIL"

def aggregate(runtime_pass:bool,parameter_state:str,tests:dict[str,str],e08:str,contract_violation:bool=False)->str:
    if contract_violation or parameter_state==PARAM_REJECTED: return CONTRACT_VIOLATION
    if parameter_state!=PARAM_ACCEPTED or not runtime_pass:
        return INCONCLUSIVE if parameter_state in {PARAM_TRUNCATED,PARAM_UNRESOLVED} else FAILED
    if any(v!="PASS" for v in tests.values()): return FAILED
    if e08=="FAIL": return FAILED
    if e08=="INCONCLUSIVE": return INCONCLUSIVE
    return QUALIFIED

def r28_filter(r27_valid:bool,runtime_pass:bool,parameter_state:str,tests:dict[str,str],e08:str,aggregate_state:str)->str:
    if aggregate_state==CONTRACT_VIOLATION or parameter_state==PARAM_REJECTED: return CONTRACT_VIOLATION
    if not r27_valid or not runtime_pass or parameter_state!=PARAM_ACCEPTED: return INCONCLUSIVE if parameter_state!=PARAM_ACCEPTED else HOLD
    if all(v=="PASS" for v in tests.values()) and e08!="FAIL" and aggregate_state==QUALIFIED: return R28_CANDIDATE
    return HOLD if aggregate_state==FAILED else INCONCLUSIVE

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--execute",action="store_true"); p.add_argument("--models",nargs="*",default=[])
    p.add_argument("--source",type=Path,default=Path("artifacts/research/r27_provenance_probe.json"))
    p.add_argument("--output",type=Path,default=Path("artifacts/research/r27_evaluation_v1.json"))
    a=p.parse_args()
    source=json.loads(a.source.read_text(encoding="utf-8")); models=[r["model_id"] for r in source.get("records",[])]
    if len(models)!=EXPECTED_R27_MODELS or len(set(models))!=EXPECTED_R27_MODELS: raise SystemExit("R27 source cardinality/uniqueness violation")
    if not a.execute:
        print("STATIC HARNESS CHECK: PASS"); print(f"R27 models: {len(models)}"); print("Runtime execution: NOT STARTED"); return 0
    import os, requests
    key=os.environ.get("ANYMODEL_API_KEY")
    if not key: raise SystemExit("ANYMODEL_API_KEY is required for --execute")
    targets=a.models or models; records=[]
    for model in targets:
        mr={"model_id":model,"tests":{}}
        for tid,prompt in VECTORS.items():
            req={"model":model,"messages":[{"role":"user","content":prompt}],**FROZEN_PARAMS}; started=time.perf_counter()
            try:
                resp=requests.post("https://anymodel.org/v1/chat/completions",headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},json=req,timeout=TIMEOUT_S)
                elapsed=time.perf_counter()-started
                try: body=resp.json()
                except ValueError: body=None
                state,diag=parameter_resolution(body,resp.status_code)
                rec={"status":state,"parameter_resolution":diag,"elapsed_s":elapsed,"input_digest":sha256_text(prompt)}
                if state==PARAM_ACCEPTED:
                    out=response_content(body)
                    if out is None: rec["status"]=INCONCLUSIVE
                    else: rec.update({"status":check(tid,out),"observed_output_digest":sha256_text(out)})
                mr["tests"][tid]=rec
            except requests.RequestException as exc:
                mr["tests"][tid]={"status":INCONCLUSIVE,"error_type":type(exc).__name__,"error":str(exc)}
        mr["e08"]="INCONCLUSIVE"
        ts={k:v["status"] for k,v in mr["tests"].items()}
        ps=PARAM_ACCEPTED if all(v.get("parameter_resolution",{}).get("output_budget_status")==PARAM_ACCEPTED for v in mr["tests"].values()) else PARAM_UNRESOLVED
        runtime=ps==PARAM_ACCEPTED and all(v=="PASS" for v in ts.values())
        mr["aggregate_state"]=aggregate(runtime,ps,ts,mr["e08"])
        mr["candidate_state"]=r28_filter(True,runtime,ps,ts,mr["e08"],mr["aggregate_state"]); records.append(mr)
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps({"contract_id":"R27-EVALUATION-v1.1","inference_parameters":FROZEN_PARAMS,"models":records},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return 0
if __name__=="__main__": raise SystemExit(main())
