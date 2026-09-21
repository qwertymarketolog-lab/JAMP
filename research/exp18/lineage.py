"""Research-only EXP-18 R2.2 multi-hop lineage inspector."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

_FORBIDDEN_KEYS = frozenset({"score", "confidence", "rank", "voting_weight"})
_DIRECTIONS = frozenset({"parents", "children"})


def build_lineage_index(
    view: Sequence[Mapping[str, Any]],
    topology_map: Mapping[str, Mapping[str, Sequence[str]]],
) -> dict[str, dict[str, tuple[str, ...]]]:
    """Build a deterministic adjacency index from an explicit topology adapter."""
    node_ids = {str(item["node_id"]) for item in view}
    index: dict[str, dict[str, tuple[str, ...]]] = {}

    for node_id in sorted(node_ids):
        topology = topology_map.get(node_id, {})
        parents = tuple(sorted(str(value) for value in topology.get("parents", ())))
        children = tuple(sorted(str(value) for value in topology.get("children", ())))
        index[node_id] = {"parents": parents, "children": children}

    return index


def inspect_lineage(
    view: Sequence[Mapping[str, Any]],
    topology_map: Mapping[str, Mapping[str, Sequence[str]]],
    *,
    start_node: str,
    direction: str,
    max_depth: int,
    conflict_context: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Return a deterministic, non-scoring lineage trace."""
    if direction not in _DIRECTIONS:
        raise ValueError(f"unsupported lineage direction: {direction!r}")
    if max_depth < 0:
        raise ValueError("max_depth must be non-negative")

    records = {str(item["node_id"]): item for item in view}
    index = build_lineage_index(view, topology_map)
    if start_node not in records:
        raise KeyError(start_node)

    forbidden = _FORBIDDEN_KEYS
    trace: list[dict[str, Any]] = []
    frontier: list[tuple[str, int]] = [(start_node, 0)]
    visited = {start_node}

    while frontier:
        node_id, depth = frontier.pop(0)
        if depth >= max_depth:
            continue

        for neighbor in index.get(node_id, {}).get(direction, ()):
            if neighbor in visited or neighbor not in records:
                continue
            visited.add(neighbor)

            source = records[neighbor]
            item = {
                key: value
                for key, value in source.items()
                if key not in forbidden
            }
            item["node_id"] = neighbor

            if conflict_context is not None:
                if conflict_context.get("collision") == "CONFLICT":
                    item["epistemic_status"] = "INCONCLUSIVE"
                elif "status" in conflict_context:
                    item["epistemic_status"] = conflict_context["status"]

            trace.append(item)
            frontier.append((neighbor, depth + 1))

    return tuple(trace)
