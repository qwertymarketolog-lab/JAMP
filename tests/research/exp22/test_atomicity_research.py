"""Research-only atomicity checks for EXP-22 observation vectors.

These tests exercise the existing EXP-21 atomization layer without changing
production/runtime behavior or defining semantic acceptance.
"""

from __future__ import annotations

from copy import deepcopy

from tests.research.exp20.fixtures_text import FIXTURES as TEXT_FIXTURES
from tests.research.exp20.fixtures_transcript import FIXTURES as TRANSCRIPT_FIXTURES
from tests.research.exp20.text_adapter import adapt as adapt_text
from tests.research.exp20.transcript_adapter import adapt as adapt_transcript
from tests.research.exp21.atomic_observation import (
    from_text_record,
    from_transcript_record,
)


def test_atomic_payload_component_shift_changes_identity() -> None:
    record = adapt_text(TEXT_FIXTURES[0])
    baseline = from_text_record(record)

    changed = deepcopy(record)
    changed["normalized_text"] = "changed atomic payload"
    candidate = from_text_record(changed)

    assert candidate.immutable_hash != baseline.immutable_hash


def test_unchanged_atomization_is_deterministic() -> None:
    record = adapt_text(TEXT_FIXTURES[0])

    first = from_text_record(record)
    second = from_text_record(deepcopy(record))

    assert first == second
    assert first.immutable_hash == second.immutable_hash


def test_composite_mutation_does_not_mask_unchanged_components() -> None:
    record = adapt_text(TEXT_FIXTURES[0])
    baseline = from_text_record(record)

    changed = deepcopy(record)
    changed["metadata"] = {
        **record["metadata"],
        "atomicity_probe": "changed",
    }
    candidate = from_text_record(changed)

    assert candidate.immutable_hash != baseline.immutable_hash
    assert candidate.source_ref == baseline.source_ref
    assert candidate.payload["normalized_text"] == baseline.payload["normalized_text"]


def test_provenance_binding_survives_transformation() -> None:
    record = adapt_text(TEXT_FIXTURES[0])
    baseline = from_text_record(record)

    changed = deepcopy(record)
    changed["source_ref"] = "fixture:text:atomicity-source-b"
    candidate = from_text_record(changed)

    assert candidate.source_ref != baseline.source_ref
    assert candidate.immutable_hash != baseline.immutable_hash


def test_transcript_atomic_boundary_changes_identity() -> None:
    record = adapt_transcript(TRANSCRIPT_FIXTURES[0])
    baseline = from_transcript_record(record)

    segment = record["segments"][0]
    changed = deepcopy(record)
    segments = list(changed["segments"])
    segments[0] = segment.__class__(
        start_ms=segment.start_ms + 1,
        end_ms=segment.end_ms,
        text=segment.text,
    )
    changed["segments"] = tuple(segments)

    candidate = from_transcript_record(changed)

    assert candidate[0].immutable_hash != baseline[0].immutable_hash


def test_atomization_payload_has_no_semantic_verdict() -> None:
    record = adapt_text(TEXT_FIXTURES[0])
    observation = from_text_record(record)

    forbidden = {"SUPPORTED", "REJECTED", "INCONCLUSIVE"}
    assert not forbidden.intersection(observation.payload)
