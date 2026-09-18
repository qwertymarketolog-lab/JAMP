from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from research.exp19.observation_relation import ObservationRelation


class ObservationAdjacencyGraph:
    """Isolated adjacency graph over canonical observation relations."""

    __slots__ = ("_edges", "_adj", "_nodes")

    def __init__(self, edges: Iterable[ObservationRelation]) -> None:
        self._edges = {
            edge.edge_hash: edge
            for edge in edges
        }
        adj: dict[str, list[str]] = {}
        nodes: set[str] = set()
        for relation in self._edges.values():
            source, target = relation.source_id, relation.target_id
            adj.setdefault(source, []).append(target)
            nodes.add(source)
            nodes.add(target)
        self._adj: dict[str, tuple[str, ...]] = {
            source: tuple(targets)
            for source, targets in adj.items()
        }
        self._nodes: frozenset[str] = frozenset(nodes)

    def is_acyclic(self) -> bool:
        adj = self._adj
        color: dict[str, int] = {node: 0 for node in self._nodes}
        nodes = tuple(self._nodes)

        for start_node in nodes:
            if color[start_node] != 0:
                continue

            color[start_node] = 1
            children = adj.get(start_node, ())
            stack = [[start_node, 0, children, len(children)]]

            while stack:
                node, index, children, length = stack[-1]
                if index < length:
                    target = children[index]
                    stack[-1][1] = index + 1
                    state = color.get(target, 2)
                    if state == 1:
                        return False
                    if state == 0:
                        color[target] = 1
                        target_children = adj.get(target, ())
                        stack.append(
                            [target, 0, target_children, len(target_children)]
                        )
                else:
                    stack.pop()
                    color[node] = 2

        return True

    def reachable(self, start_id: str) -> frozenset[str]:
        adj = self._adj
        visited: set[str] = {start_id}
        queue = deque([start_id])
        popleft = queue.popleft
        visited_add = visited.add
        queue_append = queue.append

        while queue:
            node = popleft()
            for target in adj.get(node, ()):
                if target not in visited:
                    visited_add(target)
                    queue_append(target)

        visited.discard(start_id)
        return frozenset(visited)
