from __future__ import annotations

from collections import deque
from collections.abc import Iterable

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
        self._edges = {
            edge.edge_hash: edge
            for edge in edges
        }
        nodes: set[str] = set()
        adj_map: dict[str, list[str]] = {}
        for relation in self._edges.values():
            source, target = relation.source_id, relation.target_id
            nodes.add(source)
            nodes.add(target)
            adj_map.setdefault(source, []).append(target)

        sorted_nodes = sorted(nodes)
        self._node_to_idx: dict[str, int] = {
            node: index for index, node in enumerate(sorted_nodes)
        }
        self._idx_to_node: tuple[str, ...] = tuple(sorted_nodes)
        self._v_count = len(sorted_nodes)

        adj_int = [[] for _ in range(self._v_count)]
        node_to_idx = self._node_to_idx
        for source, targets in adj_map.items():
            source_idx = node_to_idx[source]
            adj_int[source_idx] = [node_to_idx[target] for target in targets]
        self._adj_int: tuple[tuple[int, ...], ...] = tuple(
            tuple(targets) for targets in adj_int
        )

    def is_acyclic(self) -> bool:
        adj = self._adj_int
        v_count = self._v_count
        color = [0] * v_count

        for start_node in range(v_count):
            if color[start_node] != 0:
                continue

            color[start_node] = 1
            children = adj[start_node]
            stack = [[start_node, 0, children, len(children)]]

            while stack:
                frame = stack[-1]
                index = frame[1]
                if index < frame[3]:
                    target = frame[2][index]
                    frame[1] = index + 1
                    state = color[target]
                    if state == 1:
                        return False
                    if state == 0:
                        color[target] = 1
                        target_children = adj[target]
                        stack.append(
                            [target, 0, target_children, len(target_children)]
                        )
                else:
                    stack.pop()
                    color[frame[0]] = 2

        return True

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
