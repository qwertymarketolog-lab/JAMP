from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from types import MappingProxyType

from research.exp19.observation_relation import ObservationRelation


class ObservationAdjacencyGraph:
    """Isolated adjacency graph over canonical observation relations."""

    __slots__ = (
        "_edges",
        "_node_to_idx",
        "_idx_to_node",
        "_adj_int",
        "_v_count",
    )

    def __init__(self, edges: Iterable[ObservationRelation]) -> None:
        edges_by_hash = {edge.edge_hash: edge for edge in edges}
        self._edges = MappingProxyType(edges_by_hash)
        nodes: set[str] = set()
        adj_map: dict[str, list[str]] = {}
        for relation in self._edges.values():
            source, target = relation.source_id, relation.target_id
            nodes.add(source)
            nodes.add(target)
            adj_map.setdefault(source, []).append(target)

        sorted_nodes = sorted(nodes)
        self._node_to_idx: dict[str, int] = {node: index for index, node in enumerate(sorted_nodes)}
        self._idx_to_node: tuple[str, ...] = tuple(sorted_nodes)
        self._v_count = len(sorted_nodes)

        adj_int = [[] for _ in range(self._v_count)]
        node_to_idx = self._node_to_idx
        for source, targets in adj_map.items():
            source_idx = node_to_idx[source]
            adj_int[source_idx] = [node_to_idx[target] for target in targets]
        self._adj_int: tuple[tuple[int, ...], ...] = tuple(tuple(targets) for targets in adj_int)

    def is_acyclic(self) -> bool:
        adj = self._adj_int
        indegree = [0] * self._v_count
        for targets in adj:
            for target in targets:
                indegree[target] += 1

        queue = deque(index for index, degree in enumerate(indegree) if degree == 0)
        visited = 0
        popleft = queue.popleft
        queue_append = queue.append

        while queue:
            node = popleft()
            visited += 1
            for target in adj[node]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue_append(target)

        return visited == self._v_count

    def reachable(self, start_id: str) -> frozenset[str]:
        node_to_idx = self._node_to_idx
        start_idx = node_to_idx.get(start_id)
        if start_idx is None:
            return frozenset()

        adj = self._adj_int
        visited = {start_idx}
        queue = deque([start_idx])
        popleft = queue.popleft
        visited_add = visited.add
        queue_append = queue.append

        while queue:
            node = popleft()
            for target in adj[node]:
                if target not in visited:
                    visited_add(target)
                    queue_append(target)

        visited.discard(start_idx)
        idx_to_node = self._idx_to_node
        return frozenset(idx_to_node[index] for index in visited)

    def subgraph_view(self, relation_type: str) -> ObservationAdjacencyGraph:
        filtered_edges = {
            key: relation
            for key, relation in self._edges.items()
            if relation.relation_type == relation_type
        }
        return ObservationAdjacencyGraph(tuple(filtered_edges.values()))
