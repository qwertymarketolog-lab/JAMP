"""Evidence-only Text-Lint observations for the P01-P41 catalogue."""

from __future__ import annotations

from typing import Any

from jamp.atomic_observation import AtomicObservation, create_atomic_observation

PATTERN_IDS = frozenset(f"P{i:02d}" for i in range(1, 42))
ATOM_TYPE = "text_pattern_observation"
OPERATOR_ID = "jamp.text_lint"
OPERATOR_VERSION = "v0"


def create_pattern_observation(
    *,
    source_ref: str,
    pattern_id: str,
    span_start: int,
    span_end: int,
    matched_text: str,
    evidence_type: str,
    context: dict[str, Any] | None = None,
) -> AtomicObservation:
    """Create one evidence-only observation; never assigns a verdict."""
    if pattern_id not in PATTERN_IDS:
        raise ValueError(f"unknown pattern_id: {pattern_id!r}")
    if not isinstance(span_start, int) or not isinstance(span_end, int):
        raise ValueError("span bounds must be integers")
    if span_start < 0 or span_end < span_start:
        raise ValueError("invalid span")
    if not isinstance(matched_text, str):
        raise ValueError("matched_text must be a string")
    if not isinstance(evidence_type, str) or not evidence_type:
        raise ValueError("evidence_type must be a non-empty string")

    content: dict[str, Any] = {
        "pattern_id": pattern_id,
        "span_start": span_start,
        "span_end": span_end,
        "matched_text": matched_text,
        "evidence_type": evidence_type,
    }
    if context is not None:
        content["context"] = context

    return create_atomic_observation(
        content=content,
        atom_type=ATOM_TYPE,
        source_ref=source_ref,
        operator_id=OPERATOR_ID,
        operator_version=OPERATOR_VERSION,
        params={"span_start": span_start, "span_end": span_end},
    )


__all__ = ["ATOM_TYPE", "OPERATOR_ID", "OPERATOR_VERSION", "PATTERN_IDS", "create_pattern_observation"]
