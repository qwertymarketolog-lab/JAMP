from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


def compute_edge_hash(
    source_id: str,
    target_id: str,
    relation_type: str,
    params: Mapping[str, Any],
) -> str:
    """Return the canonical SHA-256 identity of a directed observation edge."""
    canonical_payload = {
        "s": source_id,
        "t": target_id,
        "r": relation_type,
        "p": dict(params),
    }
    raw = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ObservationRelation:
    """Immutable directed relation between two atomic observations."""

    source_id: str
    target_id: str
    relation_type: str
    params: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.source_id == self.target_id:
            raise ValueError("Self-loops are forbidden in ObservationRelation")

    @property
    def edge_hash(self) -> str:
        return compute_edge_hash(
            self.source_id,
            self.target_id,
            self.relation_type,
            self.params,
        )


def validate_acyclic_subset(
    relations: tuple[ObservationRelation, ...],
) -> bool:
    """Validate that the supplied relation subset is acyclic.

    The validation operates only on the supplied observation IDs; it has no
    dependency on JAMP core/runtime objects.
    """
    nodes = {r.source_id for r in relations} | {r.target_id for r in relations}
    adjacency = {node: set() for node in nodes}
    indegree = {node: 0 for node in nodes}

    for relation in relations:
        if relation.target_id not in adjacency[relation.source_id]:
            adjacency[relation.source_id].add(relation.target_id)
            indegree[relation.target_id] += 1

    ready = sorted(node for node, degree in indegree.items() if degree == 0)
    visited = 0

    while ready:
        node = ready.pop(0)
        visited += 1
        for target in sorted(adjacency[node]):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
        ready.sort()

    return visited == len(nodes)
