"""Pure causal ordering and vector-clock primitives for JAMP P16.2."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import heapq
from collections.abc import Iterable, Mapping

from .event import EventNode
from .exceptions import CausalConsistencyError


class CausalRelation(str, Enum):
    """Partial-order relation between two vector clocks."""

    BEFORE = "before"
    AFTER = "after"
    CONCURRENT = "concurrent"
    EQUAL = "equal"


@dataclass(frozen=True)
class VectorClock:
    """Immutable canonical vector clock represented by sorted components."""

    components: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        normalized = tuple(sorted(self.components))
        if normalized != self.components:
            raise ValueError("VectorClock components must be canonically sorted.")
        if any(not key or value < 0 for key, value in normalized):
            raise ValueError("VectorClock components must contain non-negative values and non-empty keys.")
        if len({key for key, _ in normalized}) != len(normalized):
            raise ValueError("VectorClock components must contain unique event IDs.")

    @classmethod
    def from_mapping(cls, values: Mapping[str, int]) -> "VectorClock":
        return cls(tuple(sorted(values.items())))

    def as_dict(self) -> dict[str, int]:
        return dict(self.components)

    def value(self, event_id: str) -> int:
        return dict(self.components).get(event_id, 0)

    def merge(self, *others: "VectorClock") -> "VectorClock":
        merged = self.as_dict()
        for other in others:
            for event_id, value in other.components:
                merged[event_id] = max(merged.get(event_id, 0), value)
        return VectorClock.from_mapping(merged)

    def tick(self, event_id: str) -> "VectorClock":
        values = self.as_dict()
        values[event_id] = values.get(event_id, 0) + 1
        return VectorClock.from_mapping(values)

    def relation(self, other: "VectorClock") -> CausalRelation:
        keys = set(self.as_dict()) | set(other.as_dict())
        less = any(self.value(key) < other.value(key) for key in keys)
        greater = any(self.value(key) > other.value(key) for key in keys)
        if less and not greater:
            return CausalRelation.BEFORE
        if greater and not less:
            return CausalRelation.AFTER
        if not less and not greater:
            return CausalRelation.EQUAL
        return CausalRelation.CONCURRENT


@dataclass(frozen=True)
class CausalOrdering:
    """Deterministic causal order together with the computed vector clocks."""

    events: tuple[EventNode, ...]
    clocks: tuple[tuple[str, VectorClock], ...]

    def clock_for(self, event_id: str) -> VectorClock:
        for key, clock in self.clocks:
            if key == event_id:
                return clock
        raise KeyError(event_id)


def _prepare(events: Iterable[EventNode]) -> dict[str, EventNode]:
    nodes: dict[str, EventNode] = {}
    for event in events:
        if event.event_id in nodes:
            raise CausalConsistencyError(f"P16.2: duplicate event_id {event.event_id!r}.")
        nodes[event.event_id] = event

    for event in nodes.values():
        for parent_id in event.parent_ids:
            if parent_id not in nodes:
                raise CausalConsistencyError(
                    f"P16.2: {event.event_id} references missing parent {parent_id}."
                )
    return nodes


def sort_causal_order(events: Iterable[EventNode]) -> tuple[EventNode, ...]:
    """Return one deterministic linear extension of an EventDAG.

    Parents always precede children. Concurrent ready events are ordered by
    their canonical event digest, making the result independent of input order.
    """
    nodes = _prepare(events)
    children: dict[str, list[str]] = {event_id: [] for event_id in nodes}
    indegree = {event_id: len(node.parent_ids) for event_id, node in nodes.items()}
    for event in nodes.values():
        for parent_id in event.parent_ids:
            children[parent_id].append(event.event_id)

    ready: list[tuple[str, str]] = [
        (node.digest, event_id) for event_id, node in nodes.items() if indegree[event_id] == 0
    ]
    heapq.heapify(ready)
    ordered: list[EventNode] = []

    while ready:
        _, event_id = heapq.heappop(ready)
        ordered.append(nodes[event_id])
        for child_id in sorted(children[event_id]):
            indegree[child_id] -= 1
            if indegree[child_id] == 0:
                heapq.heappush(ready, (nodes[child_id].digest, child_id))

    if len(ordered) != len(nodes):
        raise CausalConsistencyError("P16.2: causal graph contains a cycle.")
    return tuple(ordered)


def compute_vector_clocks(events: Iterable[EventNode]) -> tuple[tuple[str, VectorClock], ...]:
    """Compute immutable vector clocks from causal parent dependencies."""
    ordered = sort_causal_order(events)
    clocks: dict[str, VectorClock] = {}
    for event in ordered:
        if event.parent_ids:
            parent_clocks = [clocks[parent_id] for parent_id in event.parent_ids]
            base = VectorClock().merge(*parent_clocks)
        else:
            base = VectorClock()
        clocks[event.event_id] = base.tick(event.event_id)
    return tuple((event_id, clocks[event_id]) for event_id in sorted(clocks))


def build_causal_ordering(events: Iterable[EventNode]) -> CausalOrdering:
    """Compute the deterministic sequence and its vector clocks."""
    ordered = sort_causal_order(events)
    clocks = compute_vector_clocks(ordered)
    return CausalOrdering(events=ordered, clocks=clocks)
