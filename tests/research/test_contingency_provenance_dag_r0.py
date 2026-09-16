"""Research-only EXP-14-R0 contract tests for Contingency ↔ Provenance DAG.

This file defines the integration boundary between the EXP-13-R0
CONTINGENCY_EVENT contract and a minimal provenance DAG model. It introduces
no production API or runtime behavior.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json

import pytest

from jamp.research.canonical import replay_hash
from tests.research.test_contingency_r0 import (
    ContingencyEventR0,
    ContractViolationError,
    EpistemicStatus,
)


@dataclass(frozen=True)
class ProvenanceNodeR0:
    """Minimal research-only DAG node with content-addressed identity."""

    event_ref: str
    parent_refs: tuple[str, ...]
    event: ContingencyEventR0


@dataclass(frozen=True)
class ProvenanceDAGR0:
    """Minimal immutable research-only provenance DAG representation."""

    nodes: tuple[ProvenanceNodeR0, ...]


def _event(*, suffix: str = "0") -> ContingencyEventR0:
    return ContingencyEventR0(
        before_state=f"search-state-{suffix}",
        expected_state=f"search-state-{suffix}-expected",
        expected_transition="derive-next-candidate",
        unexpected_observation="candidate diverged from expected transition",
        new_path=f"search-branch-jump-{suffix}",
        provenance_ref=f"sha256:{replay_hash({'event': 'exp-14-r0', 'suffix': suffix})}",
    )


def _event_ref(event: ContingencyEventR0) -> str:
    return f"sha256:{replay_hash(asdict(event))}"


def _node(
    event: ContingencyEventR0,
    *parents: str,
) -> ProvenanceNodeR0:
    parent_refs = tuple(sorted(parents))
    if len(parent_refs) != len(set(parent_refs)):
        raise ContractViolationError("duplicate parent references are forbidden")
    return ProvenanceNodeR0(
        event_ref=_event_ref(event),
        parent_refs=parent_refs,
        event=event,
    )


def _validate_node(node: ProvenanceNodeR0) -> None:
    if node.event_ref != _event_ref(node.event):
        raise ContractViolationError("event_ref must match canonical event identity")
    if node.parent_refs != tuple(sorted(node.parent_refs)):
        raise ContractViolationError("parent references must be canonically ordered")
    if len(node.parent_refs) != len(set(node.parent_refs)):
        raise ContractViolationError("duplicate parent references are forbidden")
    if node.event.contingency_event != "CONTINGENCY_EVENT":
        raise ContractViolationError("node must preserve CONTINGENCY_EVENT identity")


def _canonical_graph(graph: ProvenanceDAGR0) -> tuple[dict[str, object], ...]:
    for node in graph.nodes:
        _validate_node(node)
    return tuple(
        {
            "event_ref": node.event_ref,
            "parent_refs": node.parent_refs,
            "event": asdict(node.event),
        }
        for node in sorted(graph.nodes, key=lambda item: item.event_ref)
    )


def _serialize(graph: ProvenanceDAGR0) -> str:
    return json.dumps(_canonical_graph(graph), sort_keys=True, separators=(",", ":"))


def _replay(serialized: str) -> ProvenanceDAGR0:
    payload = json.loads(serialized)
    nodes = tuple(
        ProvenanceNodeR0(
            event_ref=item["event_ref"],
            parent_refs=tuple(item["parent_refs"]),
            event=ContingencyEventR0(
                before_state=item["event"]["before_state"],
                expected_state=item["event"]["expected_state"],
                expected_transition=item["event"]["expected_transition"],
                unexpected_observation=item["event"]["unexpected_observation"],
                new_path=item["event"]["new_path"],
                provenance_ref=item["event"]["provenance_ref"],
                controlled_replay=item["event"]["controlled_replay"],
                status=EpistemicStatus(item["event"]["status"]),
            ),
        )
        for item in payload
    )
    graph = ProvenanceDAGR0(nodes=nodes)
    for node in graph.nodes:
        _validate_node(node)
    return graph


def test_exp14_identity_is_content_addressed() -> None:
    event = _event()
    node = _node(event)

    assert node.event_ref == f"sha256:{replay_hash(asdict(event))}"


def test_exp14_parent_integrity_is_explicit_and_order_insensitive() -> None:
    parent_a = "sha256:parent-a"
    parent_b = "sha256:parent-b"
    node = _node(_event(), parent_b, parent_a)

    assert node.parent_refs == (parent_a, parent_b)
    _validate_node(node)


def test_exp14_expected_and_unexpected_boundary_is_preserved() -> None:
    event = _event()
    node = _node(event)

    assert node.event.expected_state != node.event.unexpected_observation
    assert node.event.expected_state == event.expected_state
    assert node.event.unexpected_observation == event.unexpected_observation


def test_exp14_new_path_is_a_child_transition_not_history_rewrite() -> None:
    first = _node(_event(suffix="0"))
    jumped = _node(_event(suffix="1"), first.event_ref)
    graph = ProvenanceDAGR0(nodes=(first, jumped))

    assert jumped.parent_refs == (first.event_ref,)
    assert jumped.event.new_path == "search-branch-jump-1"
    assert first.event.new_path == "search-branch-jump-0"
    _validate_node(first)
    _validate_node(jumped)


def test_exp14_replay_invariance_preserves_canonical_graph() -> None:
    first = _node(_event(suffix="0"))
    jumped = _node(_event(suffix="1"), first.event_ref)
    graph = ProvenanceDAGR0(nodes=(jumped, first))

    replayed = _replay(_serialize(graph))

    assert _canonical_graph(replayed) == _canonical_graph(graph)
    assert _serialize(replayed) == _serialize(graph)


def test_exp14_negative_duplicate_parents_are_rejected() -> None:
    with pytest.raises(ContractViolationError, match="duplicate parent references"):
        _node(_event(), "sha256:parent-a", "sha256:parent-a")


def test_exp14_negative_event_identity_mismatch_is_rejected() -> None:
    node = _node(_event())
    tampered = ProvenanceNodeR0(
        event_ref="sha256:tampered",
        parent_refs=node.parent_refs,
        event=node.event,
    )

    with pytest.raises(ContractViolationError, match="event_ref"):
        _validate_node(tampered)


def test_exp14_negative_replay_does_not_promote_epistemic_status() -> None:
    event = _event().replay(reproduced=True)
    node = _node(event)
    replayed = _replay(_serialize(ProvenanceDAGR0(nodes=(node,))))

    assert replayed.nodes[0].event.status is EpistemicStatus.INCONCLUSIVE
    assert replayed.nodes[0].event.status is not EpistemicStatus.SUPPORTED


def test_exp14_negative_repeated_replay_is_not_evidence() -> None:
    event = _event().replay(reproduced=True)
    graph = ProvenanceDAGR0(nodes=(_node(event),))

    replay_one = _replay(_serialize(graph))
    replay_two = _replay(_serialize(replay_one))

    assert replay_one.nodes[0].event.status is EpistemicStatus.INCONCLUSIVE
    assert replay_two.nodes[0].event.status is EpistemicStatus.INCONCLUSIVE
    assert replay_two.nodes[0].event.status is not EpistemicStatus.SUPPORTED
