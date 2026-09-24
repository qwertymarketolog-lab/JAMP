"""EXP-21 paired A/B observer perturbation boundary.

Runs the exact EXP-19 canonical workload from TARGET_COMMIT with the original
wall/cpu measurement boundary. A=GC observer OFF, B=GC observer ON. The only
intended condition difference is installation of the preallocated observer.
"""
from __future__ import annotations
import contextlib, gc, hashlib, json, os, platform, statistics, subprocess, time
from array import array
from pathlib import Path
from unittest.mock import patch

TARGET_COMMIT="8c6b6a40f019d727a1ef630975a2691a390affd6"
FROZEN_CORE_BLOB="0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
WORKLOAD_ID="EXP-19-CANONICAL-G4-TAIL-TRIGGER-V1"
N=40
CONTRACT_MS=15.0
MAX_GC_EVENTS=20000
REAL_PERF_NS=time.perf_counter_ns
REAL_CPU_NS=time.process_time_ns

def git(*args:str)->str:
    return subprocess.check_output(["git",*args],text=True).strip()

def workload_hash()->str:
    return "f8875a20af579bd102afaf064dbcc435cc3e6a4b82e2b28829af9ba4b2072f92"
def relation_graph(edges):
    from research.exp19.observation_relation import ObservationRelation
    from research.exp19.adjacency_graph import ObservationAdjacencyGraph
    return ObservationAdjacencyGraph(
        tuple(ObservationRelation(a,b,"adjacent",{}) for a,b in edges)
    )

def canonical_g4():
    edges=[(str(i),str(i+1)) for i in range(10000)]
    edges.extend((str(i),str(i+10000)) for i in range(10000))
    graph=relation_graph(edges)
    assert graph.is_acyclic() is True
    graph.reachable("0")

def gc_counts():
    return tuple(int(x["collections"]) for x in gc.get_stats())

def run_condition(observer_on:bool, order_index:int, lap_index:int):
    ts=array("q",[0])*MAX_GC_EVENTS
    gen=array("b",[0])*MAX_GC_EVENTS
    phase=array("b",[0])*MAX_GC_EVENTS
    count=0
    def callback(p,info):
        nonlocal count
        i=count
        if i>=MAX_GC_EVENTS: return
        ts[i]=REAL_PERF_NS()
        gen[i]=int(info.get("generation",-1))
        phase[i]=1 if p=="start" else 2
        count=i+1

    original_acyclic=__import__("research.exp19.adjacency_graph",fromlist=["ObservationAdjacencyGraph"]).ObservationAdjacencyGraph.is_acyclic
    original_reachable=__import__("research.exp19.adjacency_graph",fromlist=["ObservationAdjacencyGraph"]).ObservationAdjacencyGraph.reachable
    from research.exp19.adjacency_graph import ObservationAdjacencyGraph

    lap={}
    def traced_acyclic(self, lap=lap):
        lap["acyclic_start_ns"]=REAL_PERF_NS()
        try: return original_acyclic(self)
        finally:
            lap["acyclic_end_ns"]=REAL_PERF_NS()
            lap["acyclic_ns"]=lap["acyclic_end_ns"]-lap["acyclic_start_ns"]
    def traced_reachable(self,start_id,lap=lap):
        lap["reachable_start_ns"]=REAL_PERF_NS()
        try: return original_reachable(self,start_id)
        finally:
            lap["reachable_end_ns"]=REAL_PERF_NS()
            lap["reachable_ns"]=lap["reachable_end_ns"]-lap["reachable_start_ns"]

    before=gc_counts()
    installed=False
    try:
        if observer_on:
            gc.callbacks.append(callback); installed=True
        wall0=REAL_PERF_NS(); cpu0=REAL_CPU_NS()
        with patch.object(ObservationAdjacencyGraph,"is_acyclic",traced_acyclic),              patch.object(ObservationAdjacencyGraph,"reachable",traced_reachable):
            canonical_g4()
        wall1=REAL_PERF_NS(); cpu1=REAL_CPU_NS()
        after=gc_counts()
    finally:
        if installed:
            with contextlib.suppress(ValueError): gc.callbacks.remove(callback)

    if not all(k in lap for k in ("acyclic_ns","reachable_ns")):
        raise RuntimeError("missing component timing")
    return {
        "condition":"observer_on" if observer_on else "observer_off",
        "lap":lap_index,
        "order_index":order_index,
        "acyclic_ms":lap["acyclic_ns"]/1e6,
        "reachable_ms":lap["reachable_ns"]/1e6,
        "canonical_elapsed_ms":(lap["acyclic_ns"]+lap["reachable_ns"])/1e6,
        "wall_call_ms":(wall1-wall0)/1e6,
        "cpu_call_ms":(cpu1-cpu0)/1e6,
        "wall_cpu_delta_ms":((wall1-wall0)-(cpu1-cpu0))/1e6,
        "gc_gen0":after[0]-before[0],
        "gc_gen1":after[1]-before[1],
        "gc_gen2":after[2]-before[2],
        "gc_events":count,
        "gc_enabled_after":gc.isenabled(),
        "gc_thresholds_after":list(gc.get_threshold()),
        "callback_restored":callback not in gc.callbacks,
    }

def main():
    errors=[]
    if git("rev-parse","HEAD")!=TARGET_COMMIT: errors.append("target_commit_mismatch")
    frozen=git("hash-object","src/jamp/run.py")
    if frozen!=FROZEN_CORE_BLOB: errors.append("frozen_core_blob_mismatch")
    if workload_hash()!="f8875a20af579bd102afaf064dbcc435cc3e6a4b82e2b28829af9ba4b2072f92":
        errors.append("workload_definition_hash_mismatch")
    rows=[]
    for i in range(1,N+1):
        gc.collect()
        # Alternate execution order to avoid always putting ON or OFF first.
        first_on=(i%2==0)
        first=run_condition(first_on,0,i)
        gc.collect()
        second=run_condition(not first_on,1,i)
        rows.extend([first,second])
    by_lap={}
    for r in rows: by_lap.setdefault(r["lap"],{})[r["condition"]]=r
    paired=[]
    for i in range(1,N+1):
        a=by_lap[i]["observer_off"]; b=by_lap[i]["observer_on"]
        paired.append({
            "lap":i,
            "off_ms":a["canonical_elapsed_ms"],"on_ms":b["canonical_elapsed_ms"],
            "delta_ms":b["canonical_elapsed_ms"]-a["canonical_elapsed_ms"],
            "off_acyclic_ms":a["acyclic_ms"],"on_acyclic_ms":b["acyclic_ms"],
            "delta_acyclic_ms":b["acyclic_ms"]-a["acyclic_ms"],
            "off_reachable_ms":a["reachable_ms"],"on_reachable_ms":b["reachable_ms"],
            "delta_reachable_ms":b["reachable_ms"]-a["reachable_ms"],
            "off_gen2":a["gc_gen2"],"on_gen2":b["gc_gen2"],
            "off_wall_cpu_delta_ms":a["wall_cpu_delta_ms"],
            "on_wall_cpu_delta_ms":b["wall_cpu_delta_ms"],
        })
    deltas=[x["delta_ms"] for x in paired]
    off=[x["off_ms"] for x in paired]; on=[x["on_ms"] for x in paired]
    result={
      "status":"VERIFIED" if not errors else "FAILED_VALIDATION",
      "target_commit":TARGET_COMMIT,"frozen_core_blob":frozen,
      "workload_id":WORKLOAD_ID,
      "workload_definition_hash":workload_hash(),"n":N,
      "contract_ms":CONTRACT_MS,
      "measurement_boundary":"wall_start/cpu_start -> canonical_g4() -> wall_end/cpu_end",
      "conditions":"observer_off vs observer_on; only gc.callbacks installation differs",
      "order":"observer_on first on even laps, observer_off first on odd laps",
      "paired_summary":{
        "off_p50_ms":statistics.median(off),"on_p50_ms":statistics.median(on),
        "off_p95_ms":statistics.quantiles(off,n=20,method="inclusive")[-1],
        "on_p95_ms":statistics.quantiles(on,n=20,method="inclusive")[-1],
        "off_tails":[i+1 for i,x in enumerate(off) if x>CONTRACT_MS],
        "on_tails":[i+1 for i,x in enumerate(on) if x>CONTRACT_MS],
        "median_delta_on_minus_off_ms":statistics.median(deltas),
        "max_abs_delta_ms":max(abs(x) for x in deltas),
      },
      "validation_errors":errors,
      "rows":rows,"paired_rows":paired,
      "runner":{"os":platform.platform(),"arch":platform.machine(),"python":platform.python_version(),"cpu_count":os.cpu_count()},
    }
    out=Path("artifacts/research/exp21_paired_ab_gc_observer.json")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(result["paired_summary"],indent=2,sort_keys=True))
    return 0 if not errors else 1

if __name__=="__main__":
    raise SystemExit(main())
