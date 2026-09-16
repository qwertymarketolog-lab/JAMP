from dataclasses import replace

import pytest

from tests.research.exp07_replay import ReplayEvent
from tests.research.exp08_mutation_harness import MUTATION_IDS, baseline_events, mutate


EXPECTED_MUTATION_IDS = {
    "M1-CLOCK-A",
    "M1-CLOCK-B",
    "M2-REVERSE",
    "M2-SHUFFLE",
    "M3-PARENT-REMOVE",
    "M3-PARENT-INJECT",
    "M4-WORKER-PAYLOAD",
    "M4-JOIN-PAYLOAD",
    "M5-DELETE-WORKER",
    "M5-DELETE-JOIN",
    "M6-INJECT-WORKER",
    "M6-INJECT-JOIN",
}


def _event_by_id(events: tuple[ReplayEvent, ...], event_id: str) -> ReplayEvent:
    matches = [event for event in events if event.event_id == event_id]
    assert len(matches) == 1
    return matches[0]


def test_exp08_has_exactly_the_frozen_12_mutations():
    assert set(MUTATION_IDS) == EXPECTED_MUTATION_IDS
    assert len(MUTATION_IDS) == 12


def test_each_mutation_is_independently_applied_and_baseline_is_unchanged():
    baseline = baseline_events()
    snapshot = baseline_events()

    for mutation_id in MUTATION_IDS:
        mutated = mutate(baseline, mutation_id)
        assert baseline == snapshot
        assert mutated is not baseline


def test_unknown_mutation_is_rejected():
    with pytest.raises(ValueError, match="Unknown EXP-08 mutation"):
        mutate(baseline_events(), "M7-UNKNOWN")


def test_m1_changes_only_the_declared_logical_clock():
    baseline = baseline_events()

    mutated_a = mutate(baseline, "M1-CLOCK-A")
    changed_a = _event_by_id(mutated_a, "evt_WORKER_A")
    original_a = _event_by_id(baseline, "evt_WORKER_A")
    assert replace(changed_a, logical_clock=original_a.logical_clock) == original_a
    assert changed_a.logical_clock == 1

    mutated_b = mutate(baseline, "M1-CLOCK-B")
    changed_b = _event_by_id(mutated_b, "evt_M")
    original_b = _event_by_id(baseline, "evt_M")
    assert replace(changed_b, logical_clock=original_b.logical_clock) == original_b
    assert changed_b.logical_clock == 2


def test_m2_changes_only_physical_order():
    baseline = baseline_events()
    baseline_by_id = {event.event_id: event for event in baseline}

    for mutation_id, expected_ids in {
        "M2-REVERSE": tuple(reversed([event.event_id for event in baseline])),
        "M2-SHUFFLE": (
            "evt_M",
            "evt_WORKER_B",
            "evt_P",
            "evt_WORKER_A",
        ),
    }.items():
        mutated = mutate(baseline, mutation_id)
        assert tuple(event.event_id for event in mutated) == expected_ids
        assert {event.event_id: event for event in mutated} == baseline_by_id


def test_m3_changes_only_join_parent_ids():
    baseline = baseline_events()

    removed = mutate(baseline, "M3-PARENT-REMOVE")
    assert _event_by_id(removed, "evt_M") == replace(
        _event_by_id(baseline, "evt_M"), parent_event_ids=("evt_WORKER_A",)
    )

    injected = mutate(baseline, "M3-PARENT-INJECT")
    assert _event_by_id(injected, "evt_M") == replace(
        _event_by_id(baseline, "evt_M"),
        parent_event_ids=("evt_WORKER_A", "evt_WORKER_B", "evt_NONEXISTENT"),
    )


def test_m4_changes_only_payload():
    baseline = baseline_events()

    worker = mutate(baseline, "M4-WORKER-PAYLOAD")
    assert _event_by_id(worker, "evt_WORKER_A") == replace(
        _event_by_id(baseline, "evt_WORKER_A"), payload="Result=21"
    )

    join = mutate(baseline, "M4-JOIN-PAYLOAD")
    assert _event_by_id(join, "evt_M") == replace(
        _event_by_id(baseline, "evt_M"), payload="Merged=61"
    )


def test_m5_removes_exactly_one_declared_event():
    baseline = baseline_events()

    deleted_worker = mutate(baseline, "M5-DELETE-WORKER")
    assert len(deleted_worker) == len(baseline) - 1
    assert "evt_WORKER_A" not in {event.event_id for event in deleted_worker}

    deleted_join = mutate(baseline, "M5-DELETE-JOIN")
    assert len(deleted_join) == len(baseline) - 1
    assert "evt_M" not in {event.event_id for event in deleted_join}


def test_m6_adds_exactly_one_declared_event():
    baseline = baseline_events()

    injected_worker = mutate(baseline, "M6-INJECT-WORKER")
    assert len(injected_worker) == len(baseline) + 1
    assert _event_by_id(injected_worker, "evt_WORKER_C") == ReplayEvent(
        event_id="evt_WORKER_C",
        parent_event_ids=("evt_P",),
        causal_type="WORKER_COMPLETION",
        worker_id="worker_c",
        logical_clock=2,
        payload="Result=40",
    )

    injected_join = mutate(baseline, "M6-INJECT-JOIN")
    assert len(injected_join) == len(baseline) + 1
    assert _event_by_id(injected_join, "evt_M2") == ReplayEvent(
        event_id="evt_M2",
        parent_event_ids=("evt_WORKER_A", "evt_WORKER_B"),
        causal_type="JOIN",
        worker_id="coordinator",
        logical_clock=3,
        payload="Merged=60",
    )


def test_mutation_input_is_not_modified_even_for_nested_values():
    baseline = baseline_events()
    before = tuple(baseline)
    mutate(baseline, "M3-PARENT-INJECT")
    assert baseline == before
