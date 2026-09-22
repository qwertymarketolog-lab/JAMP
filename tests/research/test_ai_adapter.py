"""Acceptance tests for the first AI -> JAMP local integration contour."""

from __future__ import annotations

import pytest

from jamp.research.ai_adapter import (
    ingest_ai_observation,
    verify_provenance,
)


def test_ai_observation_produces_atomic_identity_and_provenance() -> None:
    observation, provenance = ingest_ai_observation(
        source_ref="ai://chatgpt/session-001",
        content={"question": "What did the model observe?", "text": "example observation"},
        params={"segment_index": 0, "runtime_note": "ignored"},
    )

    assert len(observation.id) == 64
    assert provenance["observation_id"] == observation.id
    assert provenance["source_ref"] == observation.source_ref
    assert verify_provenance(observation, provenance) is True


def test_same_ai_observation_is_deterministic() -> None:
    kwargs = {
        "source_ref": "ai://chatgpt/session-001",
        "content": {"text": "same observation"},
        "params": {"segment_index": 3},
    }
    left, left_prov = ingest_ai_observation(**kwargs)
    right, right_prov = ingest_ai_observation(**kwargs)

    assert left.id == right.id
    assert left_prov == right_prov


def test_provenance_tampering_fails_closed() -> None:
    observation, provenance = ingest_ai_observation(
        source_ref="ai://chatgpt/session-001",
        content={"text": "observation"},
    )

    tampered = dict(provenance)
    tampered["observation_id"] = "0" * 64

    assert verify_provenance(observation, tampered) is False


def test_ai_cannot_attach_verdict_semantics() -> None:
    with pytest.raises(ValueError, match="forbidden semantic key"):
        ingest_ai_observation(
            source_ref="ai://chatgpt/session-001",
            content={"text": "observation", "confidence": 0.99},
        )


def test_operational_parameters_do_not_change_identity() -> None:
    base, _ = ingest_ai_observation(
        source_ref="ai://chatgpt/session-001",
        content={"text": "observation"},
        params={"segment_index": 1, "runtime_note": "A"},
    )
    changed, _ = ingest_ai_observation(
        source_ref="ai://chatgpt/session-001",
        content={"text": "observation"},
        params={"segment_index": 1, "runtime_note": "B"},
    )

    assert base.id == changed.id
