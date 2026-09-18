"""Research-only deterministic transcript adapter for EXP-20 Step 2."""

from __future__ import annotations

import hashlib
import itertools
import re
from dataclasses import dataclass
from typing import Any

from .text_adapter import canonical_bytes, normalize_text

_TIMESTAMPED_LINE = re.compile(
    r"^(?P<start>\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+"
    r"(?P<end>\d{2}:\d{2}:\d{2}\.\d{3})\s+(?P<text>.*)$"
)


@dataclass(frozen=True)
class TranscriptObservation:
    source_ref: str
    raw_text: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class TranscriptSegment:
    start_ms: int
    end_ms: int
    text: str


def timestamp_to_ms(value: str) -> int:
    hours, minutes, seconds = value.split(":")
    whole_seconds, millis = seconds.split(".")
    return int(hours) * 3_600_000 + int(minutes) * 60_000 + int(whole_seconds) * 1_000 + int(millis)


def parse_segments(raw_text: str) -> tuple[TranscriptSegment, ...]:
    segments: list[TranscriptSegment] = []
    for line_number, line in enumerate(raw_text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        match = _TIMESTAMPED_LINE.match(stripped)
        if match is None:
            raise ValueError(f"invalid transcript line {line_number}")
        start_ms = timestamp_to_ms(match.group("start"))
        end_ms = timestamp_to_ms(match.group("end"))
        if end_ms < start_ms:
            raise ValueError(f"negative segment duration at line {line_number}")
        segments.append(
            TranscriptSegment(
                start_ms=start_ms,
                end_ms=end_ms,
                text=normalize_text(match.group("text")),
            )
        )
    return tuple(segments)


def format_timestamp(milliseconds: int) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def reconstruct_timeline(segments: tuple[TranscriptSegment, ...]) -> str:
    return "\n".join(
        f"{format_timestamp(segment.start_ms)} --> "
        f"{format_timestamp(segment.end_ms)} {segment.text}"
        for segment in segments
    )


def reconstruction_loss(
    expected: tuple[TranscriptSegment, ...],
    actual: tuple[TranscriptSegment, ...],
) -> int:
    sentinel = object()
    pairs = itertools.zip_longest(expected, actual, fillvalue=sentinel)
    return sum(left != right for left, right in pairs)


def provenance_digest(
    observation: TranscriptObservation,
    segments: tuple[TranscriptSegment, ...],
    adapter_id: str = "exp20.transcript",
    adapter_version: str = "0.1",
) -> str:
    envelope = {
        "source_ref": observation.source_ref,
        "source_type": "transcript",
        "adapter_id": adapter_id,
        "adapter_version": adapter_version,
        "segments": [
            {
                "start_ms": segment.start_ms,
                "end_ms": segment.end_ms,
                "text": segment.text,
            }
            for segment in segments
        ],
        "metadata": observation.metadata,
    }
    return hashlib.sha256(canonical_bytes(envelope)).hexdigest()


def adapt(observation: TranscriptObservation) -> dict[str, Any]:
    segments = parse_segments(observation.raw_text)
    return {
        "source_ref": observation.source_ref,
        "source_type": "transcript",
        "adapter_id": "exp20.transcript",
        "adapter_version": "0.1",
        "segments": segments,
        "provenance_hash": provenance_digest(observation, segments),
    }
