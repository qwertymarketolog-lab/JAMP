"""PREDICTION Schema v0.

Research-only, deterministic, content-addressed prediction contract.
A prediction is defined before execution and contains no observed result,
run metadata, or mutable pointer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .canonical import canonical_bytes, replay_hash

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_TARGET_METRIC_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_EXPECTED_DIRECTIONS = frozenset({"DECREASE", "INCREASE", "NO_CHANGE"})


class PredictionIntegrityError(ValueError):
    """Raised when a PredictionRecord violates Schema v0."""


class ExpectedDirection(str, Enum):  # noqa: UP042
    DECREASE = "DECREASE"
    INCREASE = "INCREASE"
    NO_CHANGE = "NO_CHANGE"


def _validate_hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise PredictionIntegrityError(f"{field} must be lowercase SHA-256")
    return value


def _canonical_metric(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or not _TARGET_METRIC_RE.fullmatch(value)
    ):
        raise PredictionIntegrityError("target_metric must be a canonical snake_case identifier")
    return value


def _canonical_direction(value: str | ExpectedDirection) -> str:
    direction = value.value if isinstance(value, ExpectedDirection) else value
    if direction not in _EXPECTED_DIRECTIONS:
        raise PredictionIntegrityError("invalid expected_direction")
    return direction


def compute_prediction_hash(
    hypothesis_ref: str,
    target_metric: str,
    expected_direction: str | ExpectedDirection,
) -> str:
    """Return the SHA-256 content hash for Prediction Schema v0."""
    material = {
        "expected_direction": _canonical_direction(expected_direction),
        "hypothesis_ref": _validate_hash(hypothesis_ref, "hypothesis_ref"),
        "target_metric": _canonical_metric(target_metric),
    }
    return replay_hash(material)


@dataclass(frozen=True, slots=True)
class PredictionRecord:
    hypothesis_ref: str
    target_metric: str
    expected_direction: str | ExpectedDirection
    prediction_hash: str

    def __post_init__(self) -> None:
        hypothesis_ref = _validate_hash(self.hypothesis_ref, "hypothesis_ref")
        target_metric = _canonical_metric(self.target_metric)
        expected_direction = _canonical_direction(self.expected_direction)
        prediction_hash = _validate_hash(self.prediction_hash, "prediction_hash")
        object.__setattr__(self, "hypothesis_ref", hypothesis_ref)
        object.__setattr__(self, "target_metric", target_metric)
        object.__setattr__(self, "expected_direction", ExpectedDirection(expected_direction))
        if (
            compute_prediction_hash(hypothesis_ref, target_metric, expected_direction)
            != prediction_hash
        ):
            raise PredictionIntegrityError(
                "prediction_hash does not match content"
            )

    def canonical_payload(self) -> dict[str, str]:
        """Return the exact hash material, excluding the derived hash itself."""
        return {
            "expected_direction": self.expected_direction.value,
            "hypothesis_ref": self.hypothesis_ref,
            "target_metric": self.target_metric,
        }

    def canonical_bytes(self) -> bytes:
        """Return deterministic bytes used to derive prediction_hash."""
        return canonical_bytes(self.canonical_payload())

    @property
    def prediction_id(self) -> str:
        return self.prediction_hash

    def export(self) -> dict[str, str]:
        """Export the frozen content-addressed record."""
        payload = dict(self.canonical_payload())
        payload["prediction_hash"] = self.prediction_hash
        return payload


__all__ = (
    "ExpectedDirection",
    "PredictionIntegrityError",
    "PredictionRecord",
    "compute_prediction_hash",
)
