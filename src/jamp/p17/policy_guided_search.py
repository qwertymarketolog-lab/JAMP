"""Deterministic policy-injection boundary for P17.5.

The search boundary consumes an already-computed immutable policy state. It does
not own policy adaptation, replay, or historical EventDAG mutation.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from ..domain.event import canonical_json, sha256_text
from .dynamic_policy import PolicyWeights
from .policy_event import PolicyUpdateEvent, policy_state_digest


@dataclass(frozen=True)
class PolicyGuidedSearchResult:
    """Immutable canonical result of one policy-guided search execution."""

    policy_digest: str
    policy_event_id: str | None
    trajectory_digest: str
    _effective_weights: tuple[tuple[str, float], ...]
    _canonical_payload: tuple[tuple[str, Any], ...]

    @property
    def effective_weights(self) -> Mapping[str, float]:
        return MappingProxyType(dict(self._effective_weights))

    @property
    def canonical_payload(self) -> dict[str, Any]:
        return dict(self._canonical_payload)


@dataclass(frozen=True, slots=True)
class PolicyGuidedSearch:
    """Stateless deterministic execution bridge for an explicit policy state."""

    def run(
        self,
        genesis_id: str,
        policy: PolicyWeights,
        *,
        policy_event: PolicyUpdateEvent | None = None,
    ) -> PolicyGuidedSearchResult:
        if not isinstance(policy, PolicyWeights):
            raise TypeError("policy must be PolicyWeights")
        if not isinstance(genesis_id, str) or not genesis_id:
            raise ValueError("genesis_id must be a non-empty string")

        values = dict(policy.values)
        if not values:
            raise ValueError("policy weights cannot be empty")
        if any(value < policy.min_weight for value in values.values()):
            raise ValueError("policy exploration floor violated")
        if abs(sum(values.values()) - policy.total_budget) > 1e-12:
            raise ValueError("policy budget is not normalized")

        policy_digest = policy_state_digest(policy)
        policy_event_id: str | None = None
        if policy_event is not None:
            if policy_event.new_state_digest != policy_digest:
                raise ValueError("policy_event does not bind to the supplied policy")
            policy_event_id = policy_event.event_id

        effective_weights = tuple(sorted((str(name), float(value)) for name, value in values.items()))
        # The trajectory is a canonical execution binding, not a second policy
        # calculation: identical Genesis + policy + causal event produce the
        # identical trajectory; changing the active policy changes the digest.
        payload = {
            "genesis_id": genesis_id,
            "policy_digest": policy_digest,
            "policy_event_id": policy_event_id,
            "effective_weights": [[name, value] for name, value in effective_weights],
            "total_budget": policy.total_budget,
            "min_weight": policy.min_weight,
        }
        trajectory_digest = sha256_text(canonical_json(payload))

        return PolicyGuidedSearchResult(
            policy_digest=policy_digest,
            policy_event_id=policy_event_id,
            trajectory_digest=trajectory_digest,
            _effective_weights=effective_weights,
            _canonical_payload=tuple(sorted(payload.items())),
        )
