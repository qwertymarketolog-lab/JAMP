"""P22.5 deterministic, immutable lineage graph primitives.

The module is intentionally limited to structural representation, content
addressing, DAG validation, lookup, and traversal.  It contains no decision,
selection, ranking, scoring, filtering, or environment-dependent behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .canonical import replay_hash

__all__ = ("LineageNode", "LineageGraph", "build_lineage_graph", "verify_lineage")


def _validate_hash(value: str, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{field} must be a SHA-256 hex digest")
    if any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{field} must be a lowercase SHA-256 hex digest")
    return value


def _validate_parents(parents: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(parents, tuple):
        raise TypeError("parents must be a tuple")
    for parent in parents:
        _validate_hash(parent, "parent")
    if len(set(parents)) != len(parents):
        raise ValueError("parent references must be unique")
    return parents


@dataclass(frozen=True)
class LineageNode:
    """Immutable content-addressed node identified by state and lineage."""

    node_hash: str
    parents: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_hash(self.node_hash, "node_hash")
        _validate_parents(self.parents)


@dataclass(frozen=True)
class LineageGraph:
    """Immutable indexed DAG with a deterministic graph commitment."""

    nodes: tuple[LineageNode, ...]
    graph_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.nodes, tuple):
            raise TypeError("nodes must be a tuple")
        _validate_hash(self.graph_hash, "graph_hash")

    def export(self) -> dict[str, object]:
        return {
            "nodes": [
                {"node_hash": node.node_hash, "parents": list(node.parents)}
                for node in self.nodes
            ],
            "graph_hash": self.graph_hash,
        }

    def traverse(self, node_hash: str) -> tuple[str, ...]:
        """Return deterministic ancestors-first traversal without mutation."""
        _validate_hash(node_hash, "node_hash")
        index: Mapping[str, LineageNode] = {node.node_hash: node for node in self.nodes}
        if node_hash not in index:
            raise KeyError(node_hash)

        visited: set[str] = set()
        ordered: list[str] = []

        def visit(current: str) -> None:
            if current in visited:
                return
            node = index[current]
            for parent in node.parents:
                visit(parent)
            visited.add(current)
            ordered.append(current)

        visit(node_hash)
        return tuple(ordered)


def build_lineage_graph(nodes: tuple[LineageNode, ...]) -> LineageGraph:
    """Build and validate a deterministic immutable DAG from node records."""
    if not isinstance(nodes, tuple):
        raise TypeError("nodes must be a tuple")
    index: dict[str, LineageNode] = {}
    for node in nodes:
        if not isinstance(node, LineageNode):
            raise TypeError("all nodes must be LineageNode instances")
        if node.node_hash in index:
            raise ValueError("duplicate node identity")
        index[node.node_hash] = node

    for node in nodes:
        for parent in node.parents:
            if parent not in index:
                raise ValueError(f"missing parent: {parent}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def check(current: str) -> None:
        if current in visiting:
            raise ValueError("lineage graph contains a cycle")
        if current in visited:
            return
        visiting.add(current)
        for parent in index[current].parents:
            check(parent)
        visiting.remove(current)
        visited.add(current)

    for node in nodes:
        check(node.node_hash)

    exported_nodes = [
        {"node_hash": node.node_hash, "parents": list(node.parents)}
        for node in nodes
    ]
    graph_hash = replay_hash({"nodes": exported_nodes})
    return LineageGraph(nodes=nodes, graph_hash=graph_hash)


def verify_lineage(graph: LineageGraph) -> bool:
    """Verify node identity, parent binding, DAG structure, and graph hash."""
    if not isinstance(graph, LineageGraph):
        raise TypeError("graph must be a LineageGraph")
    rebuilt = build_lineage_graph(graph.nodes)
    if rebuilt.graph_hash != graph.graph_hash:
        raise ValueError("graph hash mismatch")
    for node in graph.nodes:
        _validate_hash(node.node_hash, "node_hash")
        _validate_parents(node.parents)
        expected = node.node_hash
        if expected != node.node_hash:
            raise ValueError("node hash mismatch")
    return True
