"""Minimal AI -> EXP-22 atomic observation -> provenance adapter.

The AI is an observation source only. This adapter assigns no verdict and does
not modify the JAMP run loop.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from jamp.atomic_observation import AtomicObservation, create_atomic_observation

PROVENANCE_SCHEMA = "ai-observation-provenance-v0"
ADAPTER_VERSION = "v0"


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def create_ai_observation(
    *,
    source_ref: str,
    content: Any,
    atom_type: str = "ai_observation",
    operator_id: str = "ai.adapter",
    operator_version: str = ADAPTER_VERSION,
    params: dict[str, Any] | None = None,
) -> AtomicObservation:
    """Convert one AI observation into an EXP-22 content-addressed atom."""
    return create_atomic_observation(
        content=content,
        atom_type=atom_type,
        source_ref=source_ref,
        operator_id=operator_id,
        operator_version=operator_version,
        params={} if params is None else params,
    )


def build_provenance(observation: AtomicObservation) -> dict[str, Any]:
    """Create a deterministic provenance envelope for one observation."""
    envelope = {
        "schema": PROVENANCE_SCHEMA,
        "adapter_version": ADAPTER_VERSION,
        "source_ref": observation.source_ref,
        "observation_id": observation.id,
    }
    payload = _canonical(envelope).encode("utf-8")
    return {
        **envelope,
        "provenance_hash": hashlib.sha256(payload).hexdigest(),
    }


def ingest_ai_observation(
    *,
    source_ref: str,
    content: Any,
    atom_type: str = "ai_observation",
    operator_id: str = "ai.adapter",
    operator_version: str = ADAPTER_VERSION,
    params: dict[str, Any] | None = None,
) -> tuple[AtomicObservation, dict[str, Any]]:
    """Create and provenance-bind one AI observation."""
    observation = create_ai_observation(
        source_ref=source_ref,
        content=content,
        atom_type=atom_type,
        operator_id=operator_id,
        operator_version=operator_version,
        params=params,
    )
    return observation, build_provenance(observation)


def verify_provenance(observation: AtomicObservation, provenance: Mapping[str, Any]) -> bool:
    """Fail closed unless provenance binds exactly to the observation."""
    expected = build_provenance(observation)
    return dict(provenance) == expected
