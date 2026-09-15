import hashlib
from pathlib import Path

from jamp.run import run
from tests.research.exp07_replay import ReplayEvent, replay
from tests.research.parallel_dag_adapter import ParallelDAGAdapter, ParallelDAGState

EXPECTED_CORE_BLOB_SHA = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
EXPECTED_DAG_HASH = "a932483abc58e7f71c1f14859f270181a2b05f8d2d967840b6e9d21b4baddd75"


def _recorded_log(*, reverse_workers: bool = False) -> tuple[ReplayEvent, ...]:
    worker_events = (
        ReplayEvent(
            event_id="evt_WORKER_A",
            parent_event_ids=("evt_P",),
            causal_type="WORKER_COMPLETION",
            worker_id="worker_a",
            logical_clock=2,
            payload="Result=20",
        ),
        ReplayEvent(
            event_id="evt_WORKER_B",
            parent_event_ids=("evt_P",),
            causal_type="WORKER_COMPLETION",
            worker_id="worker_b",
            logical_clock=2,
            payload="Result=40",
        ),
    )
    if reverse_workers:
        worker_events = tuple(reversed(worker_events))

    return (
        ReplayEvent(
            event_id="evt_P",
            parent_event_ids=(),
            causal_type="FORK",
            worker_id="coordinator",
            logical_clock=1,
            payload="Parent root initialized",
        ),
        *worker_events,
        ReplayEvent(
            event_id="evt_M",
            parent_event_ids=("evt_WORKER_A", "evt_WORKER_B"),
            causal_type="JOIN",
            worker_id="coordinator",
            logical_clock=3,
            payload="Merged=60",
        ),
    )


def _capture_from_exp06_adapter() -> tuple[ReplayEvent, ...]:
    recorded = run(ParallelDAGAdapter(ParallelDAGState(delay_a=0.0, delay_b=0.0)))
    return tuple(
        ReplayEvent(
            event_id=event.event_id,
            parent_event_ids=event.parent_event_ids,
            causal_type=event.causal_type,
            worker_id=event.worker_id,
            logical_clock=event.logical_clock,
            payload=event.payload,
        )
        for event in recorded.state.events
    )


def compute_git_blob_sha1(filepath: Path) -> str:
    content = filepath.read_bytes()
    header = f"blob {len(content)}\x00".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def test_r0_1_valid_recorded_log_replay():
    result = replay(_recorded_log())
    assert result.merged_result == "Merged=60"
    assert [event.event_id for event in result.canonical_events] == [
        "evt_P",
        "evt_WORKER_A",
        "evt_WORKER_B",
        "evt_M",
    ]


def test_r0_2_reverse_physical_order_is_canonicalized_identically():
    result_a = replay(_recorded_log())
    result_b = replay(_recorded_log(reverse_workers=True))

    assert result_a.canonical_events == result_b.canonical_events
    assert result_a.dag_hash == result_b.dag_hash
    assert result_a.merged_result == result_b.merged_result == "Merged=60"


def test_r0_3_replay_does_not_execute_workers(monkeypatch):
    recorded_log = _capture_from_exp06_adapter()

    def raise_if_called(*_args, **_kwargs):
        raise AssertionError("EXP-06 worker execution must not run during EXP-07 replay")

    monkeypatch.setattr(ParallelDAGAdapter, "_worker_task", raise_if_called)

    result = replay(recorded_log)
    assert result.dag_hash == EXPECTED_DAG_HASH
    assert result.merged_result == "Merged=60"


def test_r0_4_matches_fixed_canonical_reference():
    result = replay(_recorded_log())
    assert result.dag_hash == EXPECTED_DAG_HASH
    assert result.merged_result == "Merged=60"


def test_r0_core_immutability_sha():
    core_path = Path("src/jamp/run.py")
    assert core_path.exists(), "src/jamp/run.py file must exist"
    assert compute_git_blob_sha1(core_path) == EXPECTED_CORE_BLOB_SHA
