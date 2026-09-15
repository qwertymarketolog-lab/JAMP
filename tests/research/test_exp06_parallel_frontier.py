import hashlib
from pathlib import Path

from jamp.run import run
from tests.research.parallel_dag_adapter import (
    ParallelDAGAdapter,
    ParallelDAGState,
    build_canonical_dag_hash,
    canonicalize_dag_events,
)

EXPECTED_CORE_BLOB_SHA = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"


def compute_git_blob_sha1(filepath: Path) -> str:
    content = filepath.read_bytes()
    header = f"blob {len(content)}\x00".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def test_scn06_04_core_immutability_sha():
    core_path = Path("src/jamp/run.py")
    assert core_path.exists(), "src/jamp/run.py file must exist"
    actual_sha = compute_git_blob_sha1(core_path)
    assert actual_sha == EXPECTED_CORE_BLOB_SHA, f"Run Core modified! SHA mismatch: {actual_sha}"


def test_scn06_01_concurrency_execution_span_overlap():
    state = ParallelDAGState(delay_a=0.06, delay_b=0.06)
    adapter = ParallelDAGAdapter(state)
    result = run(adapter)

    spans = {s.worker_id: s for s in result.state.spans}
    span_a = spans["worker_a"]
    span_b = spans["worker_b"]

    latest_start = max(span_a.start_time, span_b.start_time)
    earliest_end = min(span_a.end_time, span_b.end_time)
    overlap = earliest_end - latest_start

    assert overlap > 0, f"Workers did not execute concurrently! Overlap: {overlap}s"


def test_scn06_02_anti_fake_concurrency_guard():
    delay_a = 0.05
    delay_b = 0.05
    state = ParallelDAGState(delay_a=delay_a, delay_b=delay_b)
    adapter = ParallelDAGAdapter(state)

    result = run(adapter)
    spans = {s.worker_id: s for s in result.state.spans}

    start_all = min(s.start_time for s in spans.values())
    end_all = max(s.end_time for s in spans.values())
    total_elapsed = end_all - start_all
    sum_delays = delay_a + delay_b

    assert total_elapsed < sum_delays, f"Fake parallelism detected: elapsed {total_elapsed}s >= sum {sum_delays}s"


def test_scn06_03_canonical_lineage_replay():
    # Run 1: Physical completion WB -> WA
    res_b_first = run(
        ParallelDAGAdapter(ParallelDAGState(delay_a=0.06, delay_b=0.01))
    )

    # Run 2: Physical completion WA -> WB
    res_a_first = run(
        ParallelDAGAdapter(ParallelDAGState(delay_a=0.01, delay_b=0.06))
    )

    # 1. Verify physical arrival order difference in raw State.events
    phys_b_first = [e.worker_id for e in res_b_first.state.events if e.causal_type == "WORKER_COMPLETION"]
    phys_a_first = [e.worker_id for e in res_a_first.state.events if e.causal_type == "WORKER_COMPLETION"]
    assert phys_b_first[0] == "worker_b", "Expected WB physical arrival first"
    assert phys_a_first[0] == "worker_a", "Expected WA physical arrival first"

    # 2. Verify Causal Lamport Logical Clock invariance (WA=2, WB=2 in both runs)
    clocks_b_first = {e.event_id: e.logical_clock for e in res_b_first.state.events}
    clocks_a_first = {e.event_id: e.logical_clock for e in res_a_first.state.events}
    assert clocks_b_first["evt_WORKER_A"] == clocks_b_first["evt_WORKER_B"] == 2
    assert clocks_a_first["evt_WORKER_A"] == clocks_a_first["evt_WORKER_B"] == 2
    assert clocks_b_first["evt_M"] == clocks_a_first["evt_M"] == 3

    # 3. Pipeline Verification: Physical Log -> Canonicalization -> DAG Hash
    canonical_b = canonicalize_dag_events(res_b_first.state.events)
    canonical_a = canonicalize_dag_events(res_a_first.state.events)
    assert canonical_b == canonical_a, "Canonical DAG event sequence must be identical"

    hash_b_first = build_canonical_dag_hash(res_b_first.state.events)
    hash_a_first = build_canonical_dag_hash(res_a_first.state.events)
    assert hash_b_first == hash_a_first, f"Canonical DAG Hash mismatch including logical_clock! {hash_b_first} != {hash_a_first}"

    # 4. Logical state equivalence
    assert res_b_first.state.merged_result == res_a_first.state.merged_result == "Merged=60"
