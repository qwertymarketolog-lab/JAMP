from __future__ import annotations

from collections import defaultdict, deque
from types import MappingProxyType

from research.exp19.observation_relation import ObservationRelation


class ObservationAdjacencyGraph:
    """Isolated adjacency graph over canonical observation relations."""

    __slots__ = ("_edges",)

    def __init__(self, edges: frozenset[ObservationRelation]) -> None:
        self._edges = MappingProxyType({edge.edge_hash: edge for edge in edges})

    def _build_adj(self) -> dict[str, list[str]]:
        adj: dict[str, list[str]] = defaultdict(list)
        for relation in self._edges.values():
            adj[relation.source_id].append(relation.target_id)
        return adj

    def is_acyclic(self) -> bool:
        adj = self._build_adj()
        nodes = {
            node
            for relation in self._edges.values()
            for node in (relation.source_id, relation.target_id)
        }
        color = {node: 0 for node in nodes}

        for start in nodes:
            if color[start] != 0:
                continue

            color[start] = 1
            stack: list[tuple[str, int]] = [(start, 0)]

            while stack:
                node, index = stack[-1]
                targets = adj.get(node, ())

                if index >= len(targets):
                    color[node] = 2
                    stack.pop()
                    continue

                target = targets[index]
                stack[-1] = (node, index + 1)

                if color[target] == 1:
                    return False
                if color[target] == 0:
                    color[target] = 1
                    stack.append((target, 0))

        return True

    def reachable(self, start_id: str) -> frozenset[str]:
        adj = self._build_adj()
        visited: set[str] = set()
        queue = deque([start_id])
        while queue:
            node = queue.popleft()
            for target in adj.get(node, ()):
                if target not in visited:
                    visited.add(target)
                    queue.append(target)
        return frozenset(visited)
