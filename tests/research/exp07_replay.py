import hashlib
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class ReplayEvent:
    event_id: str
    parent_event_ids: Tuple[str, ...]
    causal_type: str
    worker_id: str
    logical_clock: int
    payload: str


@dataclass(frozen=True)
class ReplayResult:
    canonical_events: Tuple[ReplayEvent, ...]
    dag_hash: str
    merged_result: str


def canonicalize_events(events: Tuple[ReplayEvent, ...]) -> Tuple[ReplayEvent, ...]:
    """Canonicalize a recorded physical log without executing its producers."""
    return tuple(
        sorted(
            events,
            key=lambda event: (
                event.logical_clock,
                event.event_id,
                sorted(event.parent_event_ids),
                event.causal_type,
            ),
        )
    )


def canonical_dag_hash(events: Tuple[ReplayEvent, ...]) -> str:
    canonical_events = canonicalize_events(events)
    representation = "|".join(
        "clock={}:id={}:parents={}:type={}:worker={}:payload={}".format(
            event.logical_clock,
            event.event_id,
            ",".join(sorted(event.parent_event_ids)),
            event.causal_type,
            event.worker_id,
            event.payload,
        )
        for event in canonical_events
    )
    return hashlib.sha256(representation.encode("utf-8")).hexdigest()


def replay(events: Tuple[ReplayEvent, ...]) -> ReplayResult:
    """Reconstruct the bounded EXP-06 result from recorded events only."""
    canonical_events = canonicalize_events(events)
    join_events = [event for event in canonical_events if event.causal_type == "JOIN"]
    if len(join_events) != 1:
        raise ValueError("R0 replay requires exactly one JOIN event")

    return ReplayResult(
        canonical_events=canonical_events,
        dag_hash=canonical_dag_hash(events),
        merged_result=join_events[0].payload,
    )
