"""EXP-19 CI lap-timer diagnostic. Research-only; no production changes.

Measures the exact combined sequence and isolates GC effects.
"""
import gc
import statistics
import time

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation

EDGES = [(str(i), str(i + 1)) for i in range(10_000)]
EDGES.extend((str(i), str(i + 10_000)) for i in range(10_000))

def graph():
    return ObservationAdjacencyGraph(tuple(ObservationRelation(s, t, "adjacent", {}) for s, t in EDGES))

def combined(g, disable_gc=False):
    if disable_gc:
        gc.disable()
    else:
        gc.enable()
    t0 = time.perf_counter()
    a0 = time.perf_counter(); ac = g.is_acyclic(); a1 = time.perf_counter()
    r0 = time.perf_counter(); reach = g.reachable("0"); r1 = time.perf_counter()
    t1 = time.perf_counter()
    if disable_gc:
        gc.enable()
    return (a1-a0, r1-r0, t1-t0, ac, len(reach))

def run(disable_gc=False, repeats=5):
    rows = []
    for _ in range(repeats):
        g = graph()
        rows.append(combined(g, disable_gc))
    return rows

def show(label, rows):
    vals = [[r[i]*1000 for r in rows] for i in range(3)]
    print(label)
    for name, v in zip(("lap_acyclic_ms","lap_reachable_ms","combined_ms"), vals):
        print(f"{name}: median={statistics.median(v):.3f} min={min(v):.3f} max={max(v):.3f} samples={[round(x,3) for x in v]}")
    print(f"contract_ms=15.000 acyclic={rows[0][3]} reachable_size={rows[0][4]}")

print("EXP-19 CI LAP / GC DIAGNOSTIC — READ ONLY")
show("gc_enabled", run(False))
show("gc_disabled", run(True))
