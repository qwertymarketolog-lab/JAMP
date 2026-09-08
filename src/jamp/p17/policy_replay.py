"""Deterministic replay of immutable P17.4 policy update events."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..domain.causal import sort_causal_order
from ..domain.consistency import DAGConsistencyChecker
from ..domain.exceptions import CausalConsistencyError
from ..events.dag import EventDAG
from .dynamic_policy import PolicyWeights
from .policy_event import PolicyUpdateEvent, policy_state_digest


@dataclass(frozen=True)
class PolicyReplayResult:
    state: PolicyWeights
    state_digest: str
    event_ids: tuple[str, ...]


def _state_from_payload(payload: dict[str, Any]) -> PolicyWeights:
    state = payload["new_state"]
    values = tuple((str(name), float(value)) for name, value in state["values"])
    return PolicyWeights(
        values=values,
        total_budget=float(state["total_budget"]),
        min_weight=float(state["min_weight"]),
    )


def _verify_policy_event(event: PolicyUpdateEvent, previous: PolicyWeights) -> PolicyWeights:
    if event.previous_state_digest != policy_state_digest(previous):
        raise CausalConsistencyError(
            f"Policy replay divergence at {event.event_id}: previous state digest mismatch."
        )
    payload = dict(event.payload)
    update_material = dict(payload)
    stored_update_digest = update_material.pop("policy_update_digest", None)
    from ..domain.event import canonical_json, sha256_text
    if stored_update_digest != sha256_text(canonical_json(update_material)):
        raise CausalConsistencyError(
            f"Policy replay integrity failure at {event.event_id}: policy payload was tampered."
        )
    new_state = _state_from_payload(payload)
    if event.new_state_digest != policy_state_digest(new_state):
        raise CausalConsistencyError(
            f"Policy replay divergence at {event.event_id}: new state digest mismatch."
        )
    return new_state


class PolicyReplayEngine:
    """Replay policy state from Genesis without policy re-evaluation."""

    def replay(self, dag: EventDAG, *, genesis_state: PolicyWeights) -> PolicyReplayResult:
        DAGConsistencyChecker.validate(dag.nodes)
        ordered = sort_causal_order(dag.nodes.values())
        state = genesis_state
        event_ids: list[str] = []
        for event in ordered:
            event_ids.append(event.event_id)
            if event.event_id == EventDAG.GENESIS_ID:
                continue
            if event.event_type != "PolicyUpdateEvent":
                continue
            state = _verify_policy_event(event, state)  # type: ignore[arg-type]
        return PolicyReplayResult(
            state=state,
            state_digest=policy_state_digest(state),
            event_ids=tuple(event_ids),
        )
