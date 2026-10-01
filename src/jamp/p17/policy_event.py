"""Immutable causal fixation of P17.3 policy updates."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..domain.event import (
    EventNode,
    calculate_previous_graph_digest,
    canonical_json,
    sha256_text,
)
from ..events.dag import EventDAG
from .dynamic_policy import PolicyWeights


def _state_payload(state: PolicyWeights) -> dict[str, Any]:
    return {
        "values": [[name, value] for name, value in state.values],
        "total_budget": state.total_budget,
        "min_weight": state.min_weight,
    }


def policy_state_digest(state: PolicyWeights) -> str:
    """Canonical digest of a policy state; independent of object identity."""
    return sha256_text(canonical_json(_state_payload(state)))


def _validate_parent_ids(parent_ids: tuple[str, ...], dag: EventDAG | None) -> tuple[str, ...]:
    parents = tuple(parent_ids)
    if not parents:
        raise ValueError("PolicyUpdateEvent requires at least one causal parent.")
    if parents != tuple(sorted(parents)):
        raise ValueError("PolicyUpdateEvent parent_ids must be canonically ordered.")
    if dag is not None:
        for parent_id in parents:
            if parent_id not in dag.nodes:
                raise ValueError(f"Missing causal parent: {parent_id}")
    elif any(parent_id != EventDAG.GENESIS_ID and not parent_id.startswith("POLICY_") for parent_id in parents):
        raise ValueError("Unknown causal parent identifier.")
    return parents


@dataclass(frozen=True)
class PolicyUpdateEvent(EventNode):
    """EventNode carrying an already-computed P17.3 policy transition."""

    @classmethod
    def create(
        cls,
        *,
        event_id: str,
        parent_ids: tuple[str, ...],
        previous_state: PolicyWeights,
        new_state: PolicyWeights,
        evidence_digest: str,
        causal_source: str,
        previous_state_digest: str | None = None,
        dag: EventDAG | None = None,
    ) -> "PolicyUpdateEvent":
        parents = _validate_parent_ids(parent_ids, dag)
        expected_previous = policy_state_digest(previous_state)
        if previous_state_digest is not None and previous_state_digest != expected_previous:
            raise ValueError("previous_state_digest does not match previous_state.")

        payload = {
            "previous_state": _state_payload(previous_state),
            "new_state": _state_payload(new_state),
            "prev_state_digest": expected_previous,
            "new_state_digest": policy_state_digest(new_state),
            "evidence_digest": evidence_digest,
            "causal_source": causal_source,
        }
        payload["policy_update_digest"] = sha256_text(canonical_json(payload))

        if dag is not None:
            parents_nodes = tuple(dag.nodes[parent_id] for parent_id in parents)
            previous_graph_digest = calculate_previous_graph_digest(parents_nodes)
        elif parents == (EventDAG.GENESIS_ID,):
            genesis = EventNode(
                event_id=EventDAG.GENESIS_ID,
                event_type="GENESIS",
                payload={},
                parent_ids=(),
                previous_graph_digest=sha256_text("[]"),
                timestamp=0.0,
            )
            previous_graph_digest = calculate_previous_graph_digest((genesis,))
        else:
            previous_graph_digest = ""

        return cls(
            event_id=event_id,
            event_type="PolicyUpdateEvent",
            payload=payload,
            parent_ids=parents,
            previous_graph_digest=previous_graph_digest,
            timestamp=0.0,
        )

    @property
    def previous_state_digest(self) -> str:
        return str(self.payload["prev_state_digest"])

    @property
    def new_state_digest(self) -> str:
        return str(self.payload["new_state_digest"])

    @property
    def evidence_digest(self) -> str:
        return str(self.payload["evidence_digest"])

    @property
    def causal_source(self) -> str:
        return str(self.payload["causal_source"])

    @property
    def policy_update_digest(self) -> str:
        return str(self.payload["policy_update_digest"])
