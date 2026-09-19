"""Event DAG construction and the P16.1 formal history boundary."""
from __future__ import annotations

from typing import Any
import time

from ..domain.event import EventNode, calculate_previous_graph_digest, sha256_text


class EventDAG:
    """Append-only EventDAG with a cryptographically anchored Genesis node."""

    GENESIS_ID = "GENESIS"

    def __init__(self) -> None:
        genesis = EventNode(
            event_id=self.GENESIS_ID,
            event_type="GENESIS",
            payload={},
            parent_ids=(),
            previous_graph_digest=sha256_text("[]"),
            timestamp=0.0,
        )
        self.nodes: dict[str, EventNode] = {self.GENESIS_ID: genesis}
        self.head_ids: list[str] = [self.GENESIS_ID]

    def append_event(self, event_type: str, payload: dict[str, Any]) -> EventNode:
        event_id = f"EVT_{len(self.nodes):04d}"
        parent_ids = tuple(sorted(self.head_ids))
        parents = tuple(self.nodes[parent_id] for parent_id in parent_ids)
        node = EventNode(
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            parent_ids=parent_ids,
            previous_graph_digest=calculate_previous_graph_digest(parents),
            timestamp=time.time(),
        )
        self.nodes[event_id] = node
        self.head_ids = [event_id]
        return node
