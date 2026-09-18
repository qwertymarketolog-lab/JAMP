from __future__ import annotations

from copy import deepcopy

from tests.research.exp20.fixtures_text import FIXTURES as TEXT_FIXTURES
from tests.research.exp20.fixtures_transcript import FIXTURES as TRANSCRIPT_FIXTURES
from tests.research.exp20.text_adapter import adapt as adapt_text
from tests.research.exp20.transcript_adapter import adapt as adapt_transcript

from tests.research.exp21.atomic_observation import (
    from_text_record,
    from_transcript_record,
    observation_digest,
)


def test_determinism_is_exact_for_identical_input() -> None:
    record = adapt_text(TEXT_FIXTURES[0])
    first = from_text_record(record)
    second = from_text_record(deepcopy(record))
    assert first == second
    assert first.observation_id == first.immutable_hash


def test_payload_sensitivity_covers_text_metadata_and_provenance() -> None:
    record = adapt_text(TEXT_FIXTURES[0])
    baseline = from_text_record(record)
    for field, value in (
        ("normalized_text", "changed text"),
        ("metadata", {**record["metadata"], "integrity_probe": "changed"}),
        ("provenance_hash", "changed-provenance"),
    ):
        changed = deepcopy(record)
        changed[field] = value
        assert from_text_record(changed).immutable_hash != baseline.immutable_hash


def test_source_binding_prevents_cross_source_identity_reuse() -> None:
    record = adapt_text(TEXT_FIXTURES[0])
    baseline = from_text_record(record)
    changed = deepcopy(record)
    changed["source_ref"] = "fixture:text:other-source"
    assert from_text_record(changed).immutable_hash != baseline.immutable_hash


def test_transcript_boundary_fields_change_identity() -> None:
    record = adapt_transcript(TRANSCRIPT_FIXTURES[0])
    baseline = from_transcript_record(record)
    segment = record["segments"][0]
    for field, value in (
        ("start_ms", segment.start_ms + 1),
        ("end_ms", segment.end_ms + 1),
        ("text", segment.text + " changed"),
    ):
        changed = deepcopy(record)
        changed["segments"][0] = segment.__class__(
            start_ms=value if field == "start_ms" else segment.start_ms,
            end_ms=value if field == "end_ms" else segment.end_ms,
            text=value if field == "text" else segment.text,
        )
        assert from_transcript_record(changed)[0].immutable_hash != baseline[0].immutable_hash


def test_segment_index_is_identity_bound() -> None:
    record = adapt_transcript(TRANSCRIPT_FIXTURES[0])
    observations = from_transcript_record(record)
    assert len(observations) > 1
    assert observations[0].immutable_hash != observations[1].immutable_hash
    assert observations[0].payload["segment_index"] != observations[1].payload["segment_index"]


def test_same_payload_from_different_sources_cannot_collide() -> None:
    record = adapt_text(TEXT_FIXTURES[0])
    first = from_text_record(record)
    second_record = deepcopy(record)
    second_record["source_ref"] = "fixture:text:collision-probe"
    second = from_text_record(second_record)
    assert first.payload == second.payload
    assert first.immutable_hash != second.immutable_hash


def test_atomization_has_no_semantic_verdict_fields() -> None:
    record = adapt_text(TEXT_FIXTURES[0])
    observation = from_text_record(record)
    forbidden = {"SUPPORTED", "REJECTED", "INCONCLUSIVE"}
    assert not forbidden.intersection(observation.payload)
    assert not any(
        isinstance(value, str) and value in forbidden
        for value in observation.payload.values()
    )


def test_digest_binds_schema_source_and_payload() -> None:
    record = adapt_text(TEXT_FIXTURES[0])
    observation = from_text_record(record)
    assert observation.immutable_hash == observation_digest(
        observation.source_ref, observation.payload
    )
