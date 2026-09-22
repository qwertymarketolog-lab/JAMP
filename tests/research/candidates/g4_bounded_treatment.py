"""Research-only Phase 3 treatment candidate.

The candidate never imports or modifies src/jamp. Cache scope is explicit:
each measured query receives a fresh candidate instance.
"""

from __future__ import annotations

from collections import deque
from typing import Iterable

from research.exp19.observation_relation import ObservationRelation


class MemoizedReachabilityCandidate:
    """Memoized reachability candidate with explicit query isolation."""

    def __init__(self, relations: Iterable[ObservationRelation]) -> None:
        self._adj: dict[str, tuple[str, ...]] = {}
        for relation in relations:
            self._adj.setdefault(relation.source_id, []).append(relation.target_id)
        self._adj = {node: tuple(targets) for node, targets in self._adj.items()}
        self._cache: dict[str, frozenset[str]] = {}

    def reachable(self, start_id: str) -> tuple[frozenset[str], int]:
        if start_id in self._cache:
            return self._cache[start_id], 0

        if start_id not in self._adj:
            result = frozenset()
            self._cache[start_id] = result
            return result, 0

        visited = {start_id}
        queue = deque([start_id])
        inspections = 0

        while queue:
            node = queue.popleft()
            for target in self._adj.get(node, ()):
                inspections += 1
                if target not in visited:
                    visited.add(target)
                    queue.append(target)

        visited.discard(start_id)
        result = frozenset(visited)
        self._cache[start_id] = result
        return result, inspections
