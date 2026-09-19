"""Canonical EventNode representation for the JAMP State History."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Mapping


def canonical_json(value: Any) -> str:
    """Serialize JSON-compatible data deterministically."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def calculate_state_digest(payload: Mapping[str, Any]) -> str:
    """Return the canonical SHA-256 digest of an event payload."""
    return sha256_text(canonical_json(dict(payload)))


def calculate_previous_graph_digest(
    parent_nodes: tuple["EventNode", ...],
) -> str:
    """Hash the canonical ordered parent state/digest frontier."""
    frontier = [
        {
            "event_id": node.event_id,
            "state_digest": node.state_digest,
            "event_digest": node.digest,
        }
        for node in parent_nodes
    ]
    return sha256_text(canonical_json(frontier))


@dataclass(frozen=True)
class EventNode:
    event_id: str
    event_type: str
    payload: Mapping[str, Any]
    parent_ids: tuple[str, ...] = field(default_factory=tuple)
    state_digest: str = ""
    previous_graph_digest: str = ""
    timestamp: float = 0.0
    digest: str = ""

    def __post_init__(self) -> None:
        payload = dict(self.payload)
        object.__setattr__(self, "payload", payload)
        object.__setattr__(self, "parent_ids", tuple(self.parent_ids))
        if not self.state_digest:
            object.__setattr__(self, "state_digest", calculate_state_digest(payload))
        if not self.previous_graph_digest:
            object.__setattr__(
                self,
                "previous_graph_digest",
                sha256_text("[]"),
            )
        if not self.digest:
            object.__setattr__(self, "digest", self.compute_digest())

    def compute_digest(self) -> str:
        """Compute the canonical event digest from immutable event fields."""
        material = {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "parent_ids": self.parent_ids,
            "state_digest": self.state_digest,
            "previous_graph_digest": self.previous_graph_digest,
            "timestamp": self.timestamp,
        }
        return sha256_text(canonical_json(material))

    @property
    def hash(self) -> str:
        """Legacy compatibility alias for the canonical event digest."""
        return self.digest

    @property
    def parents(self) -> list[str]:
        """Compatibility view for legacy callers; the canonical field is parent_ids."""
        return list(self.parent_ids)
