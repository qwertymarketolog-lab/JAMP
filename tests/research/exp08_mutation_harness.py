from copy import deepcopy
from dataclasses import replace
from typing import Callable

from tests.research.exp07_replay import ReplayEvent
from tests.research.test_exp07_replay_r0 import _recorded_log


MUTATION_IDS = (
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
)


def baseline_events() -> tuple[ReplayEvent, ...]:
    """Return the EXP-07 recorded baseline without executing workers."""
    return deepcopy(_recorded_log())


def _replace_event(
    events: tuple[ReplayEvent, ...], event_id: str, **changes: object
) -> tuple[ReplayEvent, ...]:
    return tuple(
        replace(event, **changes) if event.event_id == event_id else event
        for event in events
    )


def _m1_clock_a(events: tuple[ReplayEvent, ...]) -> tuple[ReplayEvent, ...]:
    return _replace_event(events, "evt_WORKER_A", logical_clock=1)


def _m1_clock_b(events: tuple[ReplayEvent, ...]) -> tuple[ReplayEvent, ...]:
    return _replace_event(events, "evt_M", logical_clock=2)


def _m2_reverse(events: tuple[ReplayEvent, ...]) -> tuple[ReplayEvent, ...]:
    return tuple(reversed(events))


def _m2_shuffle(events: tuple[ReplayEvent, ...]) -> tuple[ReplayEvent, ...]:
    by_id = {event.event_id: event for event in events}
    return tuple(
        by_id[event_id]
        for event_id in (
            "evt_M",
            "evt_WORKER_B",
            "evt_P",
            "evt_WORKER_A",
        )
    )


def _m3_parent_remove(events: tuple[ReplayEvent, ...]) -> tuple[ReplayEvent, ...]:
    return _replace_event(events, "evt_M", parent_event_ids=("evt_WORKER_A",))


def _m3_parent_inject(events: tuple[ReplayEvent, ...]) -> tuple[ReplayEvent, ...]:
    return _replace_event(
        events,
        "evt_M",
        parent_event_ids=("evt_WORKER_A", "evt_WORKER_B", "evt_NONEXISTENT"),
    )


def _m4_worker_payload(events: tuple[ReplayEvent, ...]) -> tuple[ReplayEvent, ...]:
    return _replace_event(events, "evt_WORKER_A", payload="Result=21")


def _m4_join_payload(events: tuple[ReplayEvent, ...]) -> tuple[ReplayEvent, ...]:
    return _replace_event(events, "evt_M", payload="Merged=61")


def _m5_delete_worker(events: tuple[ReplayEvent, ...]) -> tuple[ReplayEvent, ...]:
    return tuple(event for event in events if event.event_id != "evt_WORKER_A")


def _m5_delete_join(events: tuple[ReplayEvent, ...]) -> tuple[ReplayEvent, ...]:
    return tuple(event for event in events if event.event_id != "evt_M")


def _m6_inject_worker(events: tuple[ReplayEvent, ...]) -> tuple[ReplayEvent, ...]:
    injected = ReplayEvent(
        event_id="evt_WORKER_C",
        parent_event_ids=("evt_P",),
        causal_type="WORKER_COMPLETION",
        worker_id="worker_c",
        logical_clock=2,
        payload="Result=40",
    )
    return (*events, injected)


def _m6_inject_join(events: tuple[ReplayEvent, ...]) -> tuple[ReplayEvent, ...]:
    injected = ReplayEvent(
        event_id="evt_M2",
        parent_event_ids=("evt_WORKER_A", "evt_WORKER_B"),
        causal_type="JOIN",
        worker_id="coordinator",
        logical_clock=3,
        payload="Merged=60",
    )
    return (*events, injected)


_MUTATORS: dict[str, Callable[[tuple[ReplayEvent, ...]], tuple[ReplayEvent, ...]]] = {
    "M1-CLOCK-A": _m1_clock_a,
    "M1-CLOCK-B": _m1_clock_b,
    "M2-REVERSE": _m2_reverse,
    "M2-SHUFFLE": _m2_shuffle,
    "M3-PARENT-REMOVE": _m3_parent_remove,
    "M3-PARENT-INJECT": _m3_parent_inject,
    "M4-WORKER-PAYLOAD": _m4_worker_payload,
    "M4-JOIN-PAYLOAD": _m4_join_payload,
    "M5-DELETE-WORKER": _m5_delete_worker,
    "M5-DELETE-JOIN": _m5_delete_join,
    "M6-INJECT-WORKER": _m6_inject_worker,
    "M6-INJECT-JOIN": _m6_inject_join,
}


def mutate(
    baseline: tuple[ReplayEvent, ...], mutation_id: str
) -> tuple[ReplayEvent, ...]:
    """Apply exactly one frozen EXP-08 mutation without changing the input."""
    try:
        mutator = _MUTATORS[mutation_id]
    except KeyError as exc:
        raise ValueError(f"Unknown EXP-08 mutation: {mutation_id}") from exc
    return mutator(deepcopy(baseline))
