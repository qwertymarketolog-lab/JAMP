"""Acceptance gates for P19.3 Research Trajectory / Causal Replay Projection."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from jamp.research.canonical import replay_hash
from jamp.research.causal import CausalEvent, CausalIntegrityError, MissingParentError
from jamp.research.replay import (
    ReplayTrace,
    ReplayTransitionError,
    ReplayUnknownEventError,
    compute_trace_hash,
    project_replay,
)



def _state(value: int) -> dict[str, int]:
    return {"value": value}


def _event(
    event_type: str,
    sequence: int,
    state: dict[str, int],
    parents: tuple[str, ...] = (),
    payload: dict[str, Any] | None = None,
) -> CausalEvent:
    return CausalEvent(
        event_type=event_type,
        sequence=sequence,
        parent_ids=parents,
        state_hash=replay_hash(state),
        payload=payload or {"value": state["value"]},
    )


def _transition(state: dict[str, int], event: CausalEvent) -> dict[str, int]:
    if event.event_type != "set":
        raise ReplayUnknownEventError(event.event_type)
    return {"value": int(event.payload["value"])}


def _chain() -> tuple[dict[str, int], CausalEvent, CausalEvent]:
    initial = _state(0)
    first = _event("set", 0, _state(1), payload={"value": 1})
    second = _event("set", 1, _state(2), (first.event_id,), {"value": 2})
    return initial, first, second


def test_gate_01_replay_trace_schema() -> None:
    initial, first, _ = _chain()
    trace = project_replay(initial, [first], _transition)
    assert isinstance(trace, ReplayTrace)
    assert trace.initial_state_hash == replay_hash(initial)
    assert trace.ordered_event_ids == (first.event_id,)
    assert trace.resulting_state_hash == first.state_hash
    assert len(trace.trace_hash) == 64


def test_gate_02_trace_is_immutable() -> None:
    initial, first, _ = _chain()
    trace = project_replay(initial, [first], _transition)
    with pytest.raises((AttributeError, TypeError)):
        trace.ordered_event_ids += ("x",)  # type: ignore[misc]


def test_gate_03_trace_canonicalization_is_stable() -> None:
    args = ("a" * 64, ("b" * 64,), "c" * 64)
    assert compute_trace_hash(*args) == compute_trace_hash(*args)


def test_gate_04_trace_hash_is_deterministic() -> None:
    initial, first, _ = _chain()
    left = project_replay(initial, [first], _transition)
    right = project_replay(initial, [first], _transition)
    assert left.trace_hash == right.trace_hash


def test_gate_05_empty_dag_is_identity_replay() -> None:
    initial = _state(7)
    trace = project_replay(initial, [], _transition)
    assert trace.ordered_event_ids == ()
    assert trace.initial_state_hash == replay_hash(initial)
    assert trace.resulting_state_hash == replay_hash(initial)


def test_gate_06_single_event_replay() -> None:
    initial, first, _ = _chain()
    trace = project_replay(initial, [first], _transition)
    assert trace.ordered_event_ids == (first.event_id,)
    assert trace.resulting_state_hash == first.state_hash


def test_gate_07_multi_event_causal_replay() -> None:
    initial, first, second = _chain()
    trace = project_replay(initial, [second, first], _transition)
    assert trace.ordered_event_ids == (first.event_id, second.event_id)
    assert trace.resulting_state_hash == second.state_hash


def test_gate_08_topological_order_is_preserved() -> None:
    initial, first, second = _chain()
    trace = project_replay(initial, [second, first], _transition)
    assert trace.ordered_event_ids.index(first.event_id) < trace.ordered_event_ids.index(second.event_id)


def test_gate_09_same_dag_produces_identical_trace() -> None:
    initial, first, second = _chain()
    a = project_replay(initial, [first, second], _transition)
    b = project_replay(initial, [second, first], _transition)
    assert a == b


def test_gate_10_input_arrival_order_independence() -> None:
    initial, first, second = _chain()
    assert project_replay(initial, [first, second], _transition).trace_hash == project_replay(
        initial, [second, first], _transition
    ).trace_hash


def test_gate_11_parent_dependency_is_enforced() -> None:
    initial = _state(0)
    missing = _event("set", 1, _state(2), ("f" * 64,), {"value": 2})
    with pytest.raises(MissingParentError):
        project_replay(initial, [missing], _transition)


def test_gate_12_state_transition_continuity_is_enforced() -> None:
    initial, first, _ = _chain()
    wrong = replace(first, state_hash=replay_hash(_state(99)))
    # state_hash is intentionally outside event identity; replay must therefore
    # detect this independent state-anchor mismatch at transition time.
    with pytest.raises(ReplayTransitionError):
        project_replay(initial, [wrong], _transition)


def test_gate_13_event_type_tamper_breaks_identity() -> None:
    initial, first, _ = _chain()
    object.__setattr__(first, "event_type", "tampered")
    with pytest.raises(CausalIntegrityError):
        project_replay(initial, [first], _transition)


def test_gate_14_parent_id_tamper_breaks_identity() -> None:
    initial, first, _ = _chain()
    object.__setattr__(first, "parent_ids", ("f" * 64,))
    with pytest.raises(CausalIntegrityError):
        project_replay(initial, [first], _transition)


def test_gate_15_payload_tamper_breaks_identity() -> None:
    initial, first, _ = _chain()
    object.__setattr__(first, "payload", {"value": 999})
    with pytest.raises(CausalIntegrityError):
        project_replay(initial, [first], _transition)


def test_gate_16_research_module_isolation() -> None:
    import jamp.research.replay as replay_module

    assert not any(name.startswith("jamp.domain") for name in replay_module.__dict__)
