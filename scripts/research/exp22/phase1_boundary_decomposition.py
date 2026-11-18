"""EXP-22 Phase 1 boundary-preserving operation decomposition."""
from __future__ import annotations
import argparse, gc, json, os, platform, random, subprocess, time
from pathlib import Path
from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation
EXPERIMENT_ID="EXP-22-PHASE1-BOUNDARY-DECOMPOSITION-V1"
WORKLOAD_SPEC_ID="EXP-21-PHASE0-G4-CANONICAL-V1"
WORKLOAD_DEFINITION_HASH="f8875a20af579bd102afaf064dbcc435cc3e6a4b82e2b28829af9ba4b2072f92"
FROZEN_CORE_BLOB="0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
N=30; DEFAULT_SEED=2201
ARTIFACT=Path("artifacts/research/exp22_phase1_boundary_decomposition.json")
def git(*a): return subprocess.check_output(["git",*a],text=True).strip()
def graph():
    e=[ObservationRelation(str(i),str(i+1),"adjacent",{}) for i in range(10000)]
    e += [ObservationRelation(str(i),str(i+10000),"adjacent",{}) for i in range(10000)]
    return ObservationAdjacencyGraph(tuple(e))
def measure(mode,g):
    aff=sorted(os.sched_getaffinity(0)); ge=gc.isenabled(); g2=gc.get_stats()[2]["collections"]
    s=time.perf_counter_ns(); cs=time.process_time_ns()
    if mode=="combined": a=g.is_acyclic(); r=g.reachable("0")
    elif mode=="acyclic_only": a=g.is_acyclic(); r=None
    else: a=None; r=g.reachable("0")
    ce=time.process_time_ns(); e=time.perf_counter_ns()
    err=[]
    if aff!=sorted(os.sched_getaffinity(0)): err.append("cpu_affinity_changed")
    if ge!=gc.isenabled(): err.append("gc_state_changed")
    if mode!="reachable_only" and a is not True: err.append("acyclicity_check_failed")
    if mode!="acyclic_only" and r is not None and len(r)!=19999: err.append("reachability_size_mismatch")
    wall=(e-s)/1e6; cpu=(ce-cs)/1e6
    return {"mode":mode,"wall_ms":wall,"cpu_ms":cpu,"non_cpu_delta_ms":wall-cpu,"gc_gen2_collections":gc.get_stats()[2]["collections"]-g2,"cpu_affinity":aff,"errors":err}
def run(target,seed):
    err=[]
    if not target: err.append("target_commit_missing")
    if target!=git("rev-parse","HEAD"): err.append("target_commit_mismatch")
    if git("hash-object","src/jamp/run.py")!=FROZEN_CORE_BLOB: err.append("frozen_core_blob_mismatch")
    runner=os.environ.get("RUNNER_NAME","")
    if not runner: err.append("runner_name_missing")
    if not hasattr(os,"sched_getaffinity"): err.append("cpu_affinity_missing")
    g=graph()
    if len(g._edges)!=20000 or len(g._idx_to_node)!=20000: err.append("workload_shape_mismatch")
    rng=random.Random(seed); obs=[]
    for i in range(1,N+1):
        order=["combined","acyclic_only","reachable_only"]; rng.shuffle(order)
        modes=[measure(m,g) for m in order]
        for m in modes: err += [f"rep_{i}_{x}" for x in m["errors"]]
        obs.append({"repetition":i,"order":order,"modes":modes})
    vals={m:[] for m in ("combined","acyclic_only","reachable_only")}
    for rep in obs:
        for m in rep["modes"]: vals[m["mode"]].append(m["wall_ms"])
    if any(len(v)!=N for v in vals.values()): err.append("mode_sample_count_mismatch")
    def med(v):
        v=sorted(v); k=len(v)//2; return v[k] if len(v)%2 else (v[k-1]+v[k])/2
    artifact={"experiment_id":EXPERIMENT_ID,"phase":1,"target_commit":target,"workload_spec_id":WORKLOAD_SPEC_ID,"workload_definition_hash":WORKLOAD_DEFINITION_HASH,"experiment_seed":seed,"n_repetitions":N,"observations":obs,"measurement_boundary":{"reference":"EXP-22-PHASE0-MEASUREMENT-BOUNDARY-V1","combined":"graph.is_acyclic() then graph.reachable(0)","components":["acyclic_only","reachable_only"],"construction":"outside_timed_region","clock_wall":"time.perf_counter_ns","clock_cpu":"time.process_time_ns"},"environment_summary":{"runner_name":runner,"runner_os":platform.platform(),"runner_arch":platform.machine(),"kernel":platform.release(),"python_version":platform.python_version(),"cpu_count_visible":os.cpu_count(),"cpu_affinity":sorted(os.sched_getaffinity(0))},"summary":{"wall_ms_median":{k:med(v) for k,v in vals.items()},"combined_minus_components_median_ms":med(vals["combined"])-med(vals["acyclic_only"])-med(vals["reachable_only"])},"status":"VERIFIED" if not err else "INCONCLUSIVE","validation_errors":err,"frozen_core_blob":FROZEN_CORE_BLOB,"interpretation":{"observed":["per-mode timing","environment","workload identity"],"verified":["integrity and completeness"] if not err else [],"inferred":[],"unknown":["causal explanation of G4 latency","whether either isolated operation is a root cause"]}}
    ARTIFACT.parent.mkdir(parents=True,exist_ok=True); ARTIFACT.write_text(json.dumps(artifact,indent=2,sort_keys=True)+"\n")
    return artifact
if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--target-commit",required=True); p.add_argument("--seed",type=int,default=DEFAULT_SEED); a=p.parse_args(); x=run(a.target_commit,a.seed); print(json.dumps(x,indent=2)); raise SystemExit(0 if x["status"]=="VERIFIED" else 1)