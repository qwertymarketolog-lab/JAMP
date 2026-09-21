"""Research-only Multi-Agent DAG R0 aggregator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research.exp18.conflict_node import AtomicObservation, ConflictResult, classify


@dataclass(frozen=True)
class DagNode:
    node_id: str
    node_type: str
    payload: Any


@dataclass(frozen=True)
class DagResult:
    nodes: tuple[DagNode, ...]
    conflict: ConflictResult


def build_dag(
    sources: tuple[tuple[AtomicObservation, ...], ...],
) -> DagResult:
    """Build the R0 leaf -> atomization -> conflict -> ledger topology."""
    leaf_nodes = tuple(
        DagNode(
            node_id=f"leaf-{index}",
            node_type="leaf",
            payload=source,
        )
        for index, source in enumerate(sources)
    )
    atom_nodes = tuple(
        DagNode(
            node_id=f"atom-{source_index}-{atom_index}",
            node_type="atomization",
            payload=atom,
        )
        for source_index, source in enumerate(sources)
        for atom_index, atom in enumerate(source)
    )
    conflict = classify(sources)
    conflict_node = DagNode(
        node_id="conflict-0",
        node_type="conflict_aggregation",
        payload=conflict,
    )
    ledger = DagNode(
        node_id="ledger-0",
        node_type="provenance_ledger",
        payload={
            "provenance": conflict.provenance,
            "discrepancies": conflict.discrepancies,
        },
    )
    return DagResult(
        nodes=leaf_nodes + atom_nodes + (conflict_node, ledger),
        conflict=conflict,
    )
