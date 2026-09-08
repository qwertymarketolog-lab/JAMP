"""Immutable, content-addressed ResearchArtifact container for P19.3.

The artifact composes the verified P19.1 canonical state primitives and the
P19.2 causal DAG without modifying either engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .canonical import canonical_bytes
from .causal import CausalEvent, topological_order


_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_PROVENANCE_KEYS = ("event_id", "state_hash")


class ResearchArtifactError(ValueError):
    """Raised when a ResearchArtifact violates its schema or lineage rules."""


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(value[key]) for key in sorted(value)})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _require_hash(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise ResearchArtifactError(f"{field_name} must be a lowercase SHA-256 hex digest")
    return value


def _freeze_records(
    records: Sequence[Mapping[str, Any]],
    *,
    name: str,
    event_ids: set[str],
    state_hash: str,
) -> tuple[Mapping[str, Any], ...]:
    frozen: list[Mapping[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise ResearchArtifactError(f"{name}[{index}] must be a mapping")
        data = dict(record)
        provenance = [key for key in _PROVENANCE_KEYS if key in data]
        if len(provenance) != 1:
            raise ResearchArtifactError(
                f"{name}[{index}] must contain exactly one provenance key: event_id or state_hash"
            )
        if "event_id" in data:
            event_id = data["event_id"]
            if not isinstance(event_id, str) or event_id not in event_ids:
                raise ResearchArtifactError(f"{name}[{index}] references an unknown event_id")
        else:
            _require_hash(data["state_hash"], f"{name}[{index}].state_hash")
            if data["state_hash"] != state_hash:
                raise ResearchArtifactError(
                    f"{name}[{index}].state_hash must match the artifact state_hash"
                )
        frozen.append(_freeze(data))
    return tuple(frozen)


@dataclass(frozen=True, slots=True)
class ResearchArtifact:
    """Immutable top-level research record composed from P19.1 and P19.2."""

    schema_version: str
    state_hash: str
    events: tuple[CausalEvent, ...]
    observations: tuple[Mapping[str, Any], ...] = ()
    hypotheses: tuple[Mapping[str, Any], ...] = ()
    actions: tuple[Mapping[str, Any], ...] = ()
    outcomes: tuple[Mapping[str, Any], ...] = ()
    reproducibility: Mapping[str, Any] = field(default_factory=dict)
    artifact_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.schema_version, str) or not self.schema_version:
            raise ResearchArtifactError("schema_version must be a non-empty string")
        state_hash = _require_hash(self.state_hash, "state_hash")
        raw_events = tuple(self.events)
        if any(not isinstance(event, CausalEvent) for event in raw_events):
            raise ResearchArtifactError("events must contain only CausalEvent instances")
        ordered_events = topological_order(raw_events)
        event_ids = {event.event_id for event in ordered_events}
        if not event_ids:
            raise ResearchArtifactError("events must contain at least one causal event")
        if state_hash not in {event.state_hash for event in ordered_events}:
            raise ResearchArtifactError("artifact state_hash must be anchored by at least one causal event")

        object.__setattr__(self, "state_hash", state_hash)
        object.__setattr__(self, "events", ordered_events)
        object.__setattr__(
            self,
            "observations",
            _freeze_records(self.observations, name="observations", event_ids=event_ids, state_hash=state_hash),
        )
        object.__setattr__(
            self,
            "hypotheses",
            _freeze_records(self.hypotheses, name="hypotheses", event_ids=event_ids, state_hash=state_hash),
        )
        object.__setattr__(
            self,
            "actions",
            _freeze_records(self.actions, name="actions", event_ids=event_ids, state_hash=state_hash),
        )
        object.__setattr__(
            self,
            "outcomes",
            _freeze_records(self.outcomes, name="outcomes", event_ids=event_ids, state_hash=state_hash),
        )
        if not isinstance(self.reproducibility, Mapping):
            raise ResearchArtifactError("reproducibility must be a mapping")
        frozen_repro = _freeze(dict(self.reproducibility))
        object.__setattr__(self, "reproducibility", frozen_repro)

        artifact_id = hashlib.sha256(canonical_bytes(self.to_dict())).hexdigest()
        object.__setattr__(self, "artifact_id", artifact_id)

    def to_dict(self) -> dict[str, Any]:
        """Return the canonicalizable artifact representation without artifact_id."""
        return {
            "schema_version": self.schema_version,
            "state_hash": self.state_hash,
            "events": [
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "sequence": event.sequence,
                    "parent_ids": list(event.parent_ids),
                    "state_hash": event.state_hash,
                    "payload": _thaw(event.payload),
                }
                for event in self.events
            ],
            "observations": [_thaw(record) for record in self.observations],
            "hypotheses": [_thaw(record) for record in self.hypotheses],
            "actions": [_thaw(record) for record in self.actions],
            "outcomes": [_thaw(record) for record in self.outcomes],
            "reproducibility": _thaw(self.reproducibility),
        }

    def canonical_bytes(self) -> bytes:
        """Return deterministic UTF-8 bytes for the complete artifact."""
        return canonical_bytes(self.to_dict())

    def replay_hash(self) -> str:
        """Expose the P19.1 state anchor carried by this artifact."""
        return self.state_hash
