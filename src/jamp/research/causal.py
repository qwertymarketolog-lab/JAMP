"""Deterministic, content-addressed causal DAG engine for P19.2."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .canonical import canonical_bytes


_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class CausalStructureError(ValueError):
    """Raised when a causal event graph violates structural invariants."""


class MissingParentError(CausalStructureError):
    """Raised when an event references a parent outside the active pool."""


class CausalCycleError(CausalStructureError):
    """Raised when the supplied event pool is cyclic."""


def _freeze_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_payload(value[key]) for key in sorted(value)})
    if isinstance(value, list):
        return tuple(_freeze_payload(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_payload(item) for item in value)
    return value


def _thaw_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_payload(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_payload(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class CausalEvent:
    """Immutable causal transition anchored to a P19.1 replay hash."""

    event_type: str
    sequence: int
    parent_ids: tuple[str, ...]
    state_hash: str
    payload: Mapping[str, Any]
    event_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.event_type, str) or not self.event_type:
            raise CausalStructureError("event_type must be a non-empty string")
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool) or self.sequence < 0:
            raise CausalStructureError("sequence must be a non-negative integer")
        if not isinstance(self.state_hash, str) or not _HASH_RE.fullmatch(self.state_hash):
            raise CausalStructureError("state_hash must be a lowercase SHA-256 hex digest")
        parents = tuple(self.parent_ids)
        if len(set(parents)) != len(parents):
            raise CausalStructureError("parent_ids must not contain duplicates")
        if any(not isinstance(parent, str) or not parent for parent in parents):
            raise CausalStructureError("parent_ids must contain non-empty strings")
        object.__setattr__(self, "parent_ids", parents)
        frozen_payload = _freeze_payload(dict(self.payload))
        if not isinstance(frozen_payload, Mapping):
            raise CausalStructureError("payload must be a mapping")
        object.__setattr__(self, "payload", frozen_payload)
        identity = {
            "event_type": self.event_type,
            "sequence": self.sequence,
            "parent_ids": list(self.parent_ids),
            "state_hash": self.state_hash,
            "payload": _thaw_payload(self.payload),
        }
        object.__setattr__(self, "event_id", hashlib.sha256(canonical_bytes(identity)).hexdigest())

    def canonical_payload(self) -> bytes:
        """Return the canonical bytes used for this event's payload."""
        return canonical_bytes(_thaw_payload(self.payload))


def validate_event_pool(events: Sequence[CausalEvent]) -> dict[str, CausalEvent]:
    """Validate IDs and parent references before graph operations."""
    pool: dict[str, CausalEvent] = {}
    for event in events:
        if event.event_id in pool:
            raise CausalStructureError(f"duplicate event_id: {event.event_id}")
        pool[event.event_id] = event
    for event in pool.values():
        for parent_id in event.parent_ids:
            if parent_id not in pool:
                raise MissingParentError(f"missing parent {parent_id} for {event.event_id}")
    return pool


def _assert_acyclic(pool: Mapping[str, CausalEvent]) -> None:
    indegree = {event_id: len(event.parent_ids) for event_id, event in pool.items()}
    children: dict[str, list[str]] = {event_id: [] for event_id in pool}
    for event in pool.values():
        for parent_id in event.parent_ids:
            children[parent_id].append(event.event_id)
    frontier = [event_id for event_id, degree in indegree.items() if degree == 0]
    visited = 0
    while frontier:
        node = frontier.pop()
        visited += 1
        for child in children[node]:
            indegree[child] -= 1
            if indegree[child] == 0:
                frontier.append(child)
    if visited != len(pool):
        raise CausalCycleError("causal event pool contains a cycle")


def topological_order(events: Sequence[CausalEvent]) -> tuple[CausalEvent, ...]:
    """Return one deterministic topological order using event_id tie-breaking."""
    pool = validate_event_pool(events)
    _assert_acyclic(pool)

    indegree = {event_id: len(event.parent_ids) for event_id, event in pool.items()}
    children: dict[str, list[str]] = {event_id: [] for event_id in pool}
    for event in pool.values():
        for parent_id in event.parent_ids:
            children[parent_id].append(event.event_id)
    for child_list in children.values():
        child_list.sort()

    frontier = sorted((event_id for event_id, degree in indegree.items() if degree == 0))
    result: list[CausalEvent] = []
    while frontier:
        event_id = frontier.pop(0)
        result.append(pool[event_id])
        for child_id in children[event_id]:
            indegree[child_id] -= 1
            if indegree[child_id] == 0:
                frontier.append(child_id)
        frontier.sort()

    if len(result) != len(pool):
        raise CausalCycleError("causal event pool contains a cycle")
    return tuple(result)


# Explicit alias for callers that prefer the domain terminology.
sort_causal_order = topological_order
