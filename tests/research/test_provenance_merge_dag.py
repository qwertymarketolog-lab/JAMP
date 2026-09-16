"""EXP-12-A research-only tests for structural provenance merge DAGs."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from jamp.research.canonical import replay_hash
from tests.research.test_evidence_record_v0 import EXPECTED_HASH, V0_001


@dataclass(frozen=True)
class ResearchMergeEvent:
    """Minimal research-only merge event; no production DAG API is introduced."""

    evidence_ref: str
    prev_event_ref: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_ref, str):
            raise TypeError("evidence_ref must be a hash reference string")
        if any(not isinstance(ref, str) for ref in self.prev_event_ref):
            raise TypeError("prev_event_ref must contain hash reference strings")
        if len(self.prev_event_ref) != len(set(self.prev_event_ref)):
            raise ValueError("duplicate parent reference")

    @property
    def canonical_parents(self) -> tuple[str, ...]:
        return tuple(sorted(self.prev_event_ref))


def _event_ref(event: ResearchMergeEvent) -> str:
    return replay_hash(
        {
            "evidence_ref": event.evidence_ref,
            "prev_event_ref": event.canonical_parents,
        }
    )


def _verify_dag(graph: dict[str, ResearchMergeEvent]) -> bool:
    if not graph:
        return False

    for node_ref, event in graph.items():
        if node_ref != _event_ref(event):
            return False
        if any(parent not in graph for parent in event.prev_event_ref):
            return False

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_ref: str) -> bool:
        if node_ref in visiting:
            return False
        if node_ref in visited:
            return True

        visiting.add(node_ref)
        for parent in graph[node_ref].prev_event_ref:
            if not visit(parent):
                return False
        visiting.remove(node_ref)
        visited.add(node_ref)
        return True

    return all(visit(node_ref) for node_ref in graph)


def _make_leaf(evidence_ref: str) -> ResearchMergeEvent:
    return ResearchMergeEvent(evidence_ref=evidence_ref)


def test_t1_canonical_parents_order() -> None:
    event_ab = ResearchMergeEvent(
        evidence_ref=EXPECTED_HASH,
        prev_event_ref=("parent-a", "parent-b"),
    )
    event_ba = ResearchMergeEvent(
        evidence_ref=EXPECTED_HASH,
        prev_event_ref=("parent-b", "parent-a"),
    )

    assert event_ab.canonical_parents == ("parent-a", "parent-b")
    assert event_ba.canonical_parents == event_ab.canonical_parents
    assert _event_ref(event_ab) == _event_ref(event_ba)


def test_t2_valid_merge() -> None:
    event_a = _make_leaf(replay_hash(V0_001))
    event_b = _make_leaf(replay_hash({"evidence_ref": "evidence-b"}))
    ref_a = _event_ref(event_a)
    ref_b = _event_ref(event_b)
    event_c = ResearchMergeEvent(
        evidence_ref=EXPECTED_HASH,
        prev_event_ref=(ref_a, ref_b),
    )
    graph = {ref_a: event_a, ref_b: event_b, _event_ref(event_c): event_c}

    assert _verify_dag(graph)


def test_t2_missing_parent() -> None:
    event = ResearchMergeEvent(
        evidence_ref=EXPECTED_HASH,
        prev_event_ref=("missing-parent",),
    )
    ref = _event_ref(event)

    assert not _verify_dag({ref: event})


def test_t2_duplicate_parent() -> None:
    with pytest.raises(ValueError, match="duplicate parent reference"):
        ResearchMergeEvent(
            evidence_ref=EXPECTED_HASH,
            prev_event_ref=("parent-a", "parent-a"),
        )


def test_t2_self_cycle() -> None:
    event = ResearchMergeEvent(
        evidence_ref=EXPECTED_HASH,
        prev_event_ref=("self",),
    )

    assert not _verify_dag({"self": event})


def test_t2_ancestor_cycle() -> None:
    event_a = ResearchMergeEvent(
        evidence_ref=EXPECTED_HASH,
        prev_event_ref=("b",),
    )
    event_b = ResearchMergeEvent(
        evidence_ref=EXPECTED_HASH,
        prev_event_ref=("a",),
    )

    assert not _verify_dag({"a": event_a, "b": event_b})


def test_t3_tamper_parent_reference() -> None:
    event_a = _make_leaf(replay_hash(V0_001))
    event_b = _make_leaf(replay_hash({"evidence_ref": "evidence-b"}))
    ref_a = _event_ref(event_a)
    ref_b = _event_ref(event_b)
    merge = ResearchMergeEvent(
        evidence_ref=EXPECTED_HASH,
        prev_event_ref=(ref_a, ref_b),
    )
    merge_ref = _event_ref(merge)
    tampered = ResearchMergeEvent(
        evidence_ref=EXPECTED_HASH,
        prev_event_ref=(ref_a, "tampered-parent"),
    )

    assert _event_ref(tampered) != merge_ref


def test_t3_tamper_evidence_reference() -> None:
    event = ResearchMergeEvent(
        evidence_ref=EXPECTED_HASH,
        prev_event_ref=("parent-a", "parent-b"),
    )
    tampered = ResearchMergeEvent(
        evidence_ref="tampered-evidence",
        prev_event_ref=event.prev_event_ref,
    )

    assert _event_ref(tampered) != _event_ref(event)


def test_t4_dag_replay_and_verification() -> None:
    event_a = _make_leaf(replay_hash(V0_001))
    event_b = _make_leaf(replay_hash({"evidence_ref": "evidence-b"}))
    ref_a = _event_ref(event_a)
    ref_b = _event_ref(event_b)
    event_c = ResearchMergeEvent(
        evidence_ref=EXPECTED_HASH,
        prev_event_ref=(ref_b, ref_a),
    )
    ref_c = _event_ref(event_c)
    original = {ref_a: event_a, ref_b: event_b, ref_c: event_c}
    persisted = [
        {
            "evidence_ref": event.evidence_ref,
            "prev_event_ref": event.prev_event_ref,
        }
        for event in original.values()
    ]
    restored = [ResearchMergeEvent(**state) for state in persisted]
    restored_refs = {_event_ref(event): event for event in restored}

    assert restored_refs.keys() == original.keys()
    assert _verify_dag(restored_refs)
    restored_parents = {ref: event.canonical_parents for ref, event in restored_refs.items()}
    original_parents = {ref: event.canonical_parents for ref, event in original.items()}
    assert restored_parents == original_parents
