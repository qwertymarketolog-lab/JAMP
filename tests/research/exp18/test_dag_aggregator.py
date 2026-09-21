"""R0 tests for the research-only Multi-Agent DAG aggregator."""

from __future__ import annotations

from research.exp18.conflict_node import AtomicObservation, CollisionType, EpistemicStatus
from research.exp18.dag_aggregator import build_dag


def atom(source: str, value: object) -> AtomicObservation:
    return AtomicObservation(
        object_ref="object-1",
        property="status",
        val_curr=value,
        provenance=f"prov-{source}",
    )


def test_multi_agent_conflict_remains_inconclusive() -> None:
    sources = (
        (atom("ai-1", "green"),),
        (atom("ai-2", "red"),),
        (atom("human", "green"),),
    )

    result = build_dag(sources)

    assert result.conflict.status is EpistemicStatus.INCONCLUSIVE
    assert result.conflict.collision is CollisionType.CONFLICT


def test_dag_contains_all_four_r0_layers() -> None:
    sources = (
        (atom("ai-1", "green"),),
        (atom("ai-2", "green"),),
        (atom("human", "green"),),
    )

    result = build_dag(sources)

    node_types = [node.node_type for node in result.nodes]
    assert node_types.count("leaf") == 3
    assert node_types.count("atomization") == 3
    assert node_types.count("conflict_aggregation") == 1
    assert node_types.count("provenance_ledger") == 1


def test_provenance_ledger_preserves_discrepancies() -> None:
    sources = (
        (atom("ai-1", "green"),),
        (atom("ai-2", "red"),),
        (atom("human", "green"),),
    )

    result = build_dag(sources)
    ledger = next(node.payload for node in result.nodes if node.node_type == "provenance_ledger")

    assert ledger["provenance"] == (
        "prov-ai-1",
        "prov-ai-2",
        "prov-human",
    )
    assert ledger["discrepancies"][0]["reason"] == "VALUE_MISMATCH"


def test_source_order_does_not_change_conflict_result() -> None:
    sources = (
        (atom("ai-1", "green"),),
        (atom("ai-2", "red"),),
        (atom("human", "green"),),
    )

    first = build_dag(sources)
    second = build_dag((sources[2], sources[0], sources[1]))

    assert first.conflict == second.conflict
