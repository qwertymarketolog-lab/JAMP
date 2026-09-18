from __future__ import annotations

from .fixtures_transcript import FIXTURES
from .transcript_adapter import (
    TranscriptSegment,
    adapt,
    parse_segments,
    provenance_digest,
    reconstruct_timeline,
    reconstruction_loss,
)


def test_timestamps_are_extracted_into_millisecond_segments() -> None:
    segments = parse_segments(FIXTURES[0].raw_text)
    assert segments == (
        TranscriptSegment(1000, 3500, "Hello, world!"),
        TranscriptSegment(3500, 5000, "This is the first segment."),
        TranscriptSegment(5000, 7250, "Café au lait."),
    )


def test_microsegmentation_is_deterministic_and_idempotent() -> None:
    first = parse_segments(FIXTURES[0].raw_text)
    second = parse_segments(FIXTURES[0].raw_text)
    assert first == second
    assert parse_segments(reconstruct_timeline(first)) == first


def test_reconstruction_loss_is_zero() -> None:
    segments = parse_segments(FIXTURES[0].raw_text)
    reconstructed = reconstruct_timeline(segments)
    reparsed = parse_segments(reconstructed)
    assert reconstruction_loss(segments, reparsed) == 0


def test_transcript_provenance_recomputes_exactly() -> None:
    observation = FIXTURES[0]
    segments = parse_segments(observation.raw_text)
    record = adapt(observation)
    assert record["provenance_hash"] == provenance_digest(observation, segments)


def test_transcript_source_change_changes_provenance_identity() -> None:
    observation = FIXTURES[0]
    segments = parse_segments(observation.raw_text)
    changed = type(observation)(
        source_ref="fixture:transcript:changed",
        raw_text=observation.raw_text,
        metadata=observation.metadata,
    )
    assert provenance_digest(observation, segments) != provenance_digest(
        changed, parse_segments(changed.raw_text)
    )
