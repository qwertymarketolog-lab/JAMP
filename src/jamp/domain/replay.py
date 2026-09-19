"""Deterministic reconstruction and historical time travel over EventDAG."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping
import hashlib

from .causal import sort_causal_order
from .consistency import DAGConsistencyChecker
from .event import EventNode, canonical_json
from .exceptions import (
    CausalConsistencyError,
    EventNotFoundError,
    ReadonlyStateError,
)
from ..events.dag import EventDAG
from ..registry.registry import Registry, RegistryRecord


@dataclass(frozen=True)
class ReadonlyRegistryRecord:
    """Immutable projection of a committed Registry record."""

    record_id: str
    kind: str
    payload: Mapping[str, Any]


def _freeze(value: Any) -> Any:
    """Recursively freeze common mutable container values."""
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


class ReadonlyRegistry:
    """Detached, immutable historical Registry snapshot."""

    def __init__(self, records: tuple[ReadonlyRegistryRecord, ...]) -> None:
        self._records = records

    @classmethod
    def from_registry(cls, registry: Registry) -> "ReadonlyRegistry":
        records = tuple(
            ReadonlyRegistryRecord(
                record_id=record.record_id,
                kind=record.kind,
                payload=_freeze(record.payload),
            )
            for record in registry.all()
        )
        return cls(records)

    def add(self, record: object) -> None:
        raise ReadonlyStateError("Historical Registry snapshots are read-only.")

    def _commit_add(self, record: object, token: object) -> None:
        raise ReadonlyStateError("Historical Registry snapshots are read-only.")

    def all(self) -> tuple[ReadonlyRegistryRecord, ...]:
        return self._records

    def by_kind(self, kind: str) -> tuple[ReadonlyRegistryRecord, ...]:
        return tuple(record for record in self._records if record.kind == kind)

    @property
    def facts(self) -> frozenset[str]:
        return frozenset(
            record.payload["statement"]
            for record in self.by_kind("fact")
            if "statement" in record.payload
        )

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            f"conflict_{record.payload['candidate_id']}": record.payload["statement"]
            for record in self.by_kind("conflict")
            if "candidate_id" in record.payload and "statement" in record.payload
        }


@dataclass(frozen=True)
class ReplayResult:
    """Immutable result of a deterministic state reconstruction."""

    registry: Registry | ReadonlyRegistry
    event_ids: tuple[str, ...]
    state_digest: str
    verified: bool
    expected_state_digest: str | None = None

    @property
    def zero_divergence(self) -> bool:
        """Whether the replayed state matches the optional reference state."""
        return (
            self.expected_state_digest is not None
            and self.state_digest == self.expected_state_digest
        )


def _registry_digest(registry: Registry | ReadonlyRegistry) -> str:
    """Hash the canonical committed Registry projection."""
    records = [
        {
            "record_id": record.record_id,
            "kind": record.kind,
            "payload": record.payload,
        }
        for record in registry.all()
    ]
    return hashlib.sha256(canonical_json(records).encode("utf-8")).hexdigest()


def _apply_event(registry: Registry, event: EventNode, token: object) -> None:
    """Apply one state-bearing event without opening a public write path."""
    if event.event_type == "FactCommitted":
        payload = dict(event.payload)
        registry._commit_add(
            RegistryRecord(
                record_id=f"FACT_{payload['candidate_id']}",
                kind="fact",
                payload={
                    "candidate_id": payload["candidate_id"],
                    "statement": payload["statement"],
                    "source_id": payload.get("source_id", ""),
                    "provenance": payload.get("provenance", {}),
                },
            ),
            token,
        )
    elif event.event_type == "ConflictDetected":
        payload = dict(event.payload)
        registry._commit_add(
            RegistryRecord(
                record_id=f"CONFLICT_{payload['candidate_id']}",
                kind="conflict",
                payload={
                    "candidate_id": payload["candidate_id"],
                    "statement": payload["statement"],
                },
            ),
            token,
        )
    elif event.event_type in {"GENESIS", "FactRejected", "FactUnverified"}:
        return
    else:
        raise CausalConsistencyError(
            f"Unsupported replay event type: {event.event_type}"
        )


def _replay_ordered(ordered: tuple[EventNode, ...]) -> Registry:
    registry = Registry()
    token = registry._commit_authority()
    for event in ordered:
        _apply_event(registry, event, token)
    return registry


class ReplayEngine:
    """Reconstruct Registry state from a formally verified EventDAG."""

    def replay(
        self,
        dag: EventDAG,
        expected_registry: Registry | None = None,
    ) -> ReplayResult:
        """Replay into an isolated Registry in deterministic causal order."""
        DAGConsistencyChecker.validate(dag.nodes)
        ordered = sort_causal_order(dag.nodes.values())
        registry = _replay_ordered(ordered)

        state_digest = _registry_digest(registry)
        expected_digest = (
            _registry_digest(expected_registry) if expected_registry is not None else None
        )
        if expected_digest is not None and state_digest != expected_digest:
            raise CausalConsistencyError(
                "Zero-Divergence violation: replayed Registry state differs from reference state."
            )

        return ReplayResult(
            registry=registry,
            event_ids=tuple(event.event_id for event in ordered),
            state_digest=state_digest,
            verified=True,
            expected_state_digest=expected_digest,
        )

    def replay_until(self, dag: EventDAG, target_event_id: str) -> ReplayResult:
        """Reconstruct only the causal history ending at ``target_event_id``."""
        if target_event_id not in dag.nodes:
            raise EventNotFoundError(
                f"EventNode not found: {target_event_id}"
            )

        # Validate the source graph before any replay mutation. This preserves
        # P16.1's tamper-detection and zero-mutation-on-failure invariant.
        DAGConsistencyChecker.validate(dag.nodes)

        ancestry: set[str] = set()
        pending = [target_event_id]
        while pending:
            event_id = pending.pop()
            if event_id in ancestry:
                continue
            ancestry.add(event_id)
            pending.extend(dag.nodes[event_id].parent_ids)

        subgraph = {
            event_id: dag.nodes[event_id]
            for event_id in ancestry
        }
        ordered = sort_causal_order(subgraph.values())
        registry = _replay_ordered(ordered)
        state_digest = _registry_digest(registry)
        snapshot = ReadonlyRegistry.from_registry(registry)

        return ReplayResult(
            registry=snapshot,
            event_ids=tuple(event.event_id for event in ordered),
            state_digest=state_digest,
            verified=True,
        )
