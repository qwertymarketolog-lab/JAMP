"""Pre-registered EXP-21 Phase 3 comparative N=100 evaluator.

Research-only. The evaluator imports research-scoped modules and does not
modify or import src/jamp. Thresholds are fixed by the Phase 3 parameter lock.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import subprocess
from pathlib import Path

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation
from tests.research.candidates.g4_bounded_treatment import MemoizedReachabilityCandidate

WORKLOAD_SPEC_ID = "EXP-21-PHASE0-G4-CANONICAL-V1"
CANONICAL_SOURCE_REF = "research/exp21-phase0-harness"
CANONICAL_SOURCE_PATH = "scripts/research/exp_gc_causality.py"
CANONICAL_SOURCE_BLOB_SHA = "5995fc4c73a985585abe99f3eea393ef60c857a9"
WORKLOAD_DEFINITION_HASH = "f8875a20af579bd102afaf064dbcc435cc3e6a4b82e2b28829af9ba4b2072f92"
SAMPLE_SIZE = 100
TARGET_MAX_THRESHOLD = 10_000
TARGET_P50_THRESHOLD = 102
ANCHOR_NODE = 0
DEFAULT_SEED_FILE = Path("tests/research/fixtures/phase2_n100_seeds.json")


def load_canonical_workload_provenance() -> dict[str, str]:
    """Bind the registered definition digest to the exact historical Git blob."""
    source_ref = f"{CANONICAL_SOURCE_REF}:{CANONICAL_SOURCE_PATH}"
    try:
        source = subprocess.check_output(["git", "show", source_ref], text=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Fatal: canonical source unavailable: {source_ref}: {exc.output.strip()}") from exc

    blob_sha = subprocess.check_output(["git", "rev-parse", source_ref], text=True, stderr=subprocess.STDOUT).strip()
    if blob_sha != CANONICAL_SOURCE_BLOB_SHA:
        raise RuntimeError(f"canonical source blob mismatch: expected {CANONICAL_SOURCE_BLOB_SHA}, actual {blob_sha}")

    marker = "CANONICAL_G4_WORKLOAD_CODE = "
    end_marker = "\\n\\nWORKLOAD_DEFINITION_HASH"
    start = source.find(marker)
    end = source.find(end_marker, start)
    if start < 0 or end < 0:
        raise RuntimeError("Fatal: canonical workload literal not found in source blob")

    literal = source[start + len(marker):end].strip()
    try:
        workload_code = json.loads(literal)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Fatal: canonical workload literal is not valid JSON/Python string") from exc

    digest = hashlib.sha256(workload_code.encode("utf-8")).hexdigest()
    if digest != WORKLOAD_DEFINITION_HASH:
        raise RuntimeError(f"canonical workload definition digest mismatch: expected {WORKLOAD_DEFINITION_HASH}, actual {digest}")

    return {"source_ref": CANONICAL_SOURCE_REF, "source_path": CANONICAL_SOURCE_PATH, "source_blob_sha": CANONICAL_SOURCE_BLOB_SHA, "workload_definition_sha256": digest}

def load_canonical_seeds(path: Path = DEFAULT_SEED_FILE) -> list[int]:
    """Load the frozen Phase 2 N=100 seed fixture; never accept external seeds."""
    assert path.exists(), f"Fatal: Missing frozen Phase 2 seed fixture at {path}"
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    seeds = payload.get("start_nodes") if isinstance(payload, dict) else payload
    assert isinstance(seeds, list), "Fixture payload must resolve to a list[int]"
    assert len(seeds) == SAMPLE_SIZE, (
        f"Expected N={SAMPLE_SIZE} unique seeds, got {len(seeds)}"
    )
    assert len(set(seeds)) == SAMPLE_SIZE, "Seed nodes contain duplicate entries"
    assert all(isinstance(x, int) and not isinstance(x, bool) for x in seeds), (
        "Seed nodes must be integers"
    )
    return seeds


def build_canonical_relations() -> tuple[ObservationRelation, ...]:
    edges = [
        ObservationRelation(str(i), str(i + 1), "adjacent", {})
        for i in range(10_000)
    ]
    edges.extend(
        ObservationRelation(str(i), str(i + 10_000), "adjacent", {})
        for i in range(10_000)
    )
    return tuple(edges)


def workload_identity(relations: tuple[ObservationRelation, ...]) -> str:
    payload = [
        {
            "s": relation.source_id,
            "t": relation.target_id,
            "r": relation.relation_type,
            "p": dict(relation.params),
        }
        for relation in relations
    ]
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def control_counts(
    graph: ObservationAdjacencyGraph, start_nodes: list[int]
) -> list[int]:
    adjacency = graph._adj_int
    node_to_idx = graph._node_to_idx
    counts: list[int] = []

    for start in start_nodes:
        start_id = str(start)
        start_idx = node_to_idx.get(start_id)
        if start_idx is None:
            counts.append(0)
            continue

        visited = {start_idx}
        queue = [start_idx]
        inspections = 0
        cursor = 0
        while cursor < len(queue):
            node = queue[cursor]
            cursor += 1
            for target in adjacency[node]:
                inspections += 1
                if target not in visited:
                    visited.add(target)
                    queue.append(target)
        counts.append(inspections)

    return counts


def treatment_counts(
    relations: tuple[ObservationRelation, ...], start_nodes: list[int]
) -> list[int]:
    counts: list[int] = []
    for start in start_nodes:
        candidate = MemoizedReachabilityCandidate(relations)
        _, inspections = candidate.reachable(str(start))
        counts.append(inspections)
    return counts


def summarize(counts: list[int]) -> dict[str, int]:
    ordered = sorted(counts)
    return {
        "n": len(counts),
        "p50": int(statistics.median(ordered)),
        "p95": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))],
        "max": max(ordered),
    }


def evaluate(output_path: Path | None = None) -> dict[str, object]:
    provenance = load_canonical_workload_provenance()
    start_nodes = load_canonical_seeds()

    relations = build_canonical_relations()
    payload_hash = workload_identity(relations)
    if payload_hash == WORKLOAD_DEFINITION_HASH:
        raise RuntimeError("payload hash unexpectedly equals definition hash")

    graph = ObservationAdjacencyGraph(relations)
    control = control_counts(graph, start_nodes)
    treatment = treatment_counts(relations, start_nodes)

    control_summary = summarize(control)
    treatment_summary = summarize(treatment)

    tail_reduction = (
        100.0 * (control_summary["max"] - treatment_summary["max"]) / control_summary["max"]
        if control_summary["max"]
        else 0.0
    )
    median_delta = (
        100.0
        * (treatment_summary["p50"] - control_summary["p50"])
        / control_summary["p50"]
        if control_summary["p50"]
        else 0.0
    )

    result: dict[str, object] = {
        "status": "EVALUATED",
        "workload_spec_id": WORKLOAD_SPEC_ID,
        "workload_definition_hash": WORKLOAD_DEFINITION_HASH,
        "workload_payload_sha256": payload_hash,
        "canonical_source": provenance,
        "sample_size": SAMPLE_SIZE,
        "anchor_node": ANCHOR_NODE,
        "start_nodes": start_nodes,
        "control": control_summary,
        "treatment": treatment_summary,
        "tail_reduction_percent": tail_reduction,
        "median_delta_percent": median_delta,
        "tail_threshold_max": TARGET_MAX_THRESHOLD,
        "p50_threshold_max": TARGET_P50_THRESHOLD,
        "tail_pass": treatment_summary["max"] <= TARGET_MAX_THRESHOLD,
        "median_pass": treatment_summary["p50"] <= TARGET_P50_THRESHOLD,
        "decision": (
            "PASS"
            if treatment_summary["max"] <= TARGET_MAX_THRESHOLD
            and treatment_summary["p50"] <= TARGET_P50_THRESHOLD
            else "NOT_CONFIRMED"
        ),
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    return result
