"""Deterministic Dynamic Policy Adaptor for P17.3."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


_EPS = 1e-12


@dataclass(frozen=True)
class PolicyWeights:
    values: tuple[tuple[str, float], ...]
    total_budget: float
    min_weight: float

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, float],
        *,
        total_budget: float,
        min_weight: float,
    ) -> "PolicyWeights":
        if not values:
            raise ValueError("policy weights cannot be empty")
        if total_budget <= 0:
            raise ValueError("budget must be positive")
        if min_weight <= 0:
            raise ValueError("floor must be positive")
        if len(values) * min_weight > total_budget + _EPS:
            raise ValueError("floor is incompatible with budget")
        if any(value < min_weight - _EPS for value in values.values()):
            raise ValueError("floor violation")
        if abs(sum(values.values()) - total_budget) > _EPS:
            raise ValueError("budget must be normalized")
        return cls(tuple(sorted((str(k), float(v)) for k, v in values.items())), float(total_budget), float(min_weight))

    def as_dict(self) -> Mapping[str, float]:
        return MappingProxyType(dict(self.values))


@dataclass(frozen=True)
class DynamicPolicyAdaptor:
    """Pure, stateless deterministic weight recalculation."""

    _weights: PolicyWeights

    def __post_init__(self) -> None:
        if not isinstance(self._weights, PolicyWeights):
            raise TypeError("weights must be PolicyWeights")

    def update(
        self,
        evidence: Mapping[str, float],
        *,
        exploitation_pressure: float = 0.0,
    ) -> Mapping[str, float]:
        current = dict(self._weights.values)
        if set(evidence) != set(current):
            raise ValueError("policy set mismatch")
        if not 0.0 <= exploitation_pressure <= 1.0:
            raise ValueError("exploitation pressure must be in [0, 1]")

        # Evidence proposes relative merit. Pressure is deliberately damped;
        # the remaining budget is distributed by a deterministic inverse-pressure
        # term so weak policies retain more exploration weight.
        scores = {name: max(float(evidence[name]), 0.0) for name in sorted(current)}
        if all(score <= _EPS for score in scores.values()):
            scores = {name: 1.0 for name in sorted(current)}

        floor = self._weights.min_weight
        budget = self._weights.total_budget
        remaining = budget - len(scores) * floor
        if remaining < -_EPS:
            raise ValueError("floor is incompatible with budget")

        total_score = sum(scores.values())
        if total_score <= _EPS:
            shares = {name: 1.0 / len(scores) for name in sorted(scores)}
        else:
            shares = {name: scores[name] / total_score for name in sorted(scores)}

        if exploitation_pressure:
            # Mix merit with uniform exploration. At pressure=1, every policy
            # receives an equal share of the non-floor budget.
            uniform = 1.0 / len(scores)
            shares = {
                name: (1.0 - exploitation_pressure) * shares[name]
                + exploitation_pressure * uniform
                for name in sorted(scores)
            }

        result = {name: floor + remaining * shares[name] for name in sorted(scores)}
        correction = budget - sum(result.values())
        first = sorted(result)[0]
        result[first] += correction

        if any(value < floor - _EPS for value in result.values()):
            raise ValueError("floor violation")
        if abs(sum(result.values()) - budget) > _EPS:
            raise ValueError("budget normalization violation")
        return MappingProxyType(result)
