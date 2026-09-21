"""Research-only EXP-18 R1 DAG query projection."""

from __future__ import annotations

from typing import Any

from research.exp18.conflict_node import AtomicObservation
from research.exp18.dag_aggregator import DagResult


def _atoms(dag: DagResult) -> tuple[AtomicObservation, ...]:
    return tuple(
        node.payload
        for node in dag.nodes
        if node.node_type == "atomization" and isinstance(node.payload, AtomicObservation)
    )


def query_subgraph(
    dag: DagResult,
    *,
    object_ref: str | None = None,
    property: str | None = None,
    provenance: str | None = None,
    discrepancy_type: str | None = None,
) -> tuple[dict[str, Any], ...]:
    """Return a deterministic, non-scoring projection of the R0 DAG."""
    discrepancies = {
        (item["object_ref"], item["property"]): item for item in dag.conflict.discrepancies
    }

    result: list[dict[str, Any]] = []

    for atom in _atoms(dag):
        if object_ref is not None and atom.object_ref != object_ref:
            continue
        if property is not None and atom.property != property:
            continue
        if provenance is not None and atom.provenance != provenance:
            continue

        key = (atom.object_ref, atom.property)

        if discrepancy_type is not None:
            if discrepancy_type != "CONFLICT":
                continue
            if key not in discrepancies:
                continue

        item: dict[str, Any] = {
            "object_ref": atom.object_ref,
            "property": atom.property,
            "value": atom.val_curr,
            "provenance": atom.provenance,
        }

        if key in discrepancies:
            item["discrepancy_type"] = "CONFLICT"

        result.append(item)

    return tuple(
        sorted(
            result,
            key=lambda item: (
                item["object_ref"],
                item["property"],
                item["provenance"],
            ),
        )
    )
