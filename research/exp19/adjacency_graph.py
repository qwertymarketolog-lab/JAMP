from __future__ import annotations

from collections import defaultdict, deque

from research.exp19.observation_relation import ObservationRelation


class ObservationAdjacencyGraph:
    """Isolated adjacency graph over canonical observation relations."""

    __slots__ = ("_edges",)

    def __init__(self, edges: frozenset[ObservationRelation]) -> None:
        self._edges = dict.fromkeys(edge.edge_hash for edge in edges)
        self._relations = tuple(edges)

    def _build_adj(self) -> dict[str, list[str]]:
        adj: dict[str, list[str]] = defaultdict(list)
        for relation in self._relations:
            adj[relation.source_id].append(relation.target_id)
        return adj

    def is_acyclic(self) -> bool:
        adj = self._build_adj()
        nodes = {node for relation in self._relations for node in (relation.source_id, relation.target_id)}
        color = {node: 0 for node in nodes}

        def dfs(node: str) -> bool:
            color[node] = 1
            for target in adj.get(node, ()):
                if color[target] == 1:
                    return False
                if color[target] == 0 and not dfs(target):
                    return False
            color[node] = 2
            return True

        return all(color[node] != 0 or dfs(node) for node in nodes)

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
