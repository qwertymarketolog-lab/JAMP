"""P19.2 acceptance gates for the isolated causal engine."""

from __future__ import annotations

import hashlib
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import pytest

from jamp.research.canonical import replay_hash
from jamp.research.causal import (
    CausalCycleError,
    CausalEvent,
    CausalIntegrityError,
    CausalStructureError,
    MissingParentError,
    _assert_acyclic,
    sort_causal_order,
    validate_event_pool,
)


def make_event(*, sequence: int = 0, parents: tuple[str, ...] = (), payload: dict | None = None) -> CausalEvent:
    return CausalEvent(
        event_type="observation",
        sequence=sequence,
        parent_ids=parents,
        state_hash=replay_hash({"state": sequence}),
        payload=payload or {"value": sequence},
    )


def test_gate_01_schema_compliance() -> None:
    event = make_event()
    assert event.event_type == "observation"
    assert event.sequence == 0
    assert isinstance(event.parent_ids, tuple)
    assert len(event.state_hash) == 64
    assert len(event.event_id) == 64


def test_gate_02_state_hash_binds_to_replay_hash() -> None:
    state = {"answer": 42, "nested": {"x": 1}}
    event = CausalEvent("state", 1, (), replay_hash(state), state)
    assert event.state_hash == replay_hash(state)


def test_gate_03_event_and_payload_are_immutable() -> None:
    event = make_event(payload={"nested": {"value": 1}})
    with pytest.raises(FrozenInstanceError):
        event.sequence = 9  # type: ignore[misc]
    with pytest.raises(TypeError):
        event.payload["nested"]["value"] = 2  # type: ignore[index]


def test_gate_04_canonical_payload_is_stable() -> None:
    first = make_event(payload={"b": 2, "a": 1})
    second = make_event(payload={"a": 1, "b": 2})
    assert first.canonical_payload() == second.canonical_payload()
    assert first.event_id == second.event_id


def test_gate_05_identical_content_has_identical_event_id() -> None:
    first = make_event(sequence=3, payload={"x": [1, 2, 3]})
    second = make_event(sequence=3, payload={"x": [1, 2, 3]})
    assert first.event_id == second.event_id


def test_gate_06_payload_change_changes_event_id() -> None:
    first = make_event(sequence=3, payload={"x": 1})
    second = make_event(sequence=3, payload={"x": 2})
    assert first.event_id != second.event_id


def test_gate_07_parent_reference_is_structural() -> None:
    parent = make_event(sequence=0)
    child = CausalEvent("observation", 1, (parent.event_id,), replay_hash({"state": 1}), {"value": 1})
    pool = validate_event_pool([parent, child])
    assert pool[child.event_id].parent_ids == (parent.event_id,)


def test_gate_08_missing_parent_is_rejected() -> None:
    missing = "0" * 64
    event = CausalEvent("observation", 1, (missing,), replay_hash({"state": 1}), {"value": 1})
    with pytest.raises(MissingParentError):
        validate_event_pool([event])


def test_gate_09_cycles_are_rejected() -> None:
    first_id = "1" * 64
    second_id = "2" * 64
    first = SimpleNamespace(event_id=first_id, parent_ids=(second_id,))
    second = SimpleNamespace(event_id=second_id, parent_ids=(first_id,))
    with pytest.raises(CausalCycleError):
        _assert_acyclic({first_id: first, second_id: second})


def test_gate_10_dag_order_respects_all_parents() -> None:
    root_a = make_event(sequence=0, payload={"root": "a"})
    root_b = make_event(sequence=0, payload={"root": "b"})
    child = CausalEvent(
        "observation",
        1,
        tuple(sorted((root_a.event_id, root_b.event_id))),
        replay_hash({"state": "child"}),
        {"value": "child"},
    )
    order = sort_causal_order([child, root_b, root_a])
    positions = {event.event_id: index for index, event in enumerate(order)}
    assert positions[root_a.event_id] < positions[child.event_id]
    assert positions[root_b.event_id] < positions[child.event_id]


def test_gate_11_frontier_tie_break_is_deterministic() -> None:
    events = [make_event(sequence=i, payload={"i": i}) for i in range(6)]
    expected = tuple(sorted(events, key=lambda event: event.event_id))
    assert sort_causal_order(list(reversed(events))) == expected
    assert sort_causal_order(events) == expected


def test_gate_12_research_module_isolation() -> None:
    causal_source = Path(__file__).resolve().parents[2] / "src" / "jamp" / "research" / "causal.py"
    source = causal_source.read_text(encoding="utf-8")
    forbidden = ("jamp.domain", "Registry", "CommitManager", "commit_manager", "registry")
    assert not any(token in source for token in forbidden)
    assert "from .canonical import canonical_bytes" in source
    assert hashlib.sha256(b"JAMP-P19.2").hexdigest()


def test_gate_13_event_type_tamper_breaks_identity_verification() -> None:
    event = make_event(sequence=4, payload={"x": 1})
    object.__setattr__(event, "event_type", "tampered")
    assert event.verify_integrity() is False
    with pytest.raises(CausalIntegrityError):
        validate_event_pool([event])


def test_gate_14_parent_tamper_breaks_identity_verification() -> None:
    parent = make_event(sequence=0, payload={"root": True})
    child = CausalEvent("observation", 1, (parent.event_id,), replay_hash({"state": 1}), {"value": 1})
    object.__setattr__(child, "parent_ids", ("f" * 64,))
    assert child.verify_integrity() is False
    with pytest.raises(CausalIntegrityError):
        validate_event_pool([parent, child])


def test_gate_15_payload_tamper_breaks_identity_verification() -> None:
    event = make_event(sequence=5, payload={"x": {"y": 1}})
    object.__setattr__(event, "payload", {"x": {"y": 2}})
    assert event.verify_integrity() is False
    with pytest.raises(CausalIntegrityError):
        validate_event_pool([event])
