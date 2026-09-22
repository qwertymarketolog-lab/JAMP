"""Acceptance tests for the Text-Lint Evidence Contract v0."""

from __future__ import annotations

import pytest

from jamp.research.text_lint import create_pattern_observation


def test_each_catalogue_entry_can_produce_an_observation() -> None:
    for pattern_number in range(1, 42):
        pattern_id = f"P{pattern_number:02d}"
        observation = create_pattern_observation(
            source_ref="document://acceptance-001",
            pattern_id=pattern_id,
            span_start=0,
            span_end=4,
            matched_text="text",
            evidence_type="syntactic",
        )
        assert observation.atom_type == "text_pattern_observation"
        assert observation.content["pattern_id"] == pattern_id
        assert len(observation.id) == 64


def test_unknown_pattern_fails_closed() -> None:
    with pytest.raises(ValueError, match="unknown pattern_id"):
        create_pattern_observation(
            source_ref="document://acceptance-001",
            pattern_id="P42",
            span_start=0,
            span_end=4,
            matched_text="text",
            evidence_type="syntactic",
        )


@pytest.mark.parametrize(("start", "end"), [(-1, 2), (3, 2)])
def test_invalid_spans_fail_closed(start: int, end: int) -> None:
    with pytest.raises(ValueError, match="invalid span"):
        create_pattern_observation(
            source_ref="document://acceptance-001",
            pattern_id="P01",
            span_start=start,
            span_end=end,
            matched_text="text",
            evidence_type="lexical",
        )


def test_semantic_verdict_is_rejected_by_exp22() -> None:
    with pytest.raises(ValueError, match="forbidden semantic key"):
        create_pattern_observation(
            source_ref="document://acceptance-001",
            pattern_id="P01",
            span_start=0,
            span_end=4,
            matched_text="text",
            evidence_type="lexical",
            context={"confidence": 0.99},
        )


def test_detector_is_deterministic() -> None:
    kwargs = {
        "source_ref": "document://acceptance-001",
        "pattern_id": "P31",
        "span_start": 10,
        "span_end": 20,
        "matched_text": "filler",
        "evidence_type": "lexical",
        "context": {"rule": "phrase-match"},
    }
    left = create_pattern_observation(**kwargs)
    right = create_pattern_observation(**kwargs)
    assert left.id == right.id


def test_contextual_metadata_is_operational_and_does_not_change_identity() -> None:
    base = create_pattern_observation(
        source_ref="document://acceptance-001",
        pattern_id="P38",
        span_start=0,
        span_end=4,
        matched_text="text",
        evidence_type="sentence-structure",
        context={"sentence_count": 3},
    )
    changed = create_pattern_observation(
        source_ref="document://acceptance-001",
        pattern_id="P38",
        span_start=0,
        span_end=4,
        matched_text="text",
        evidence_type="sentence-structure",
        context={"sentence_count": 4},
    )
    assert base.id == changed.id
