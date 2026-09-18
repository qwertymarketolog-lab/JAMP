"""Research-only structural trace comparison for EXP-26.

The comparator operates on deterministic trace metadata only. It does not
interpret semantic outcomes, call runtime/model providers, or import JAMP core.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = "exp26.multi_trace_comparison.v0"


@dataclass(frozen=True)
class TraceStep:
    step_index: int
    event_kind: str
    payload_digest: str


@dataclass(frozen=True)
class TraceStream:
    agent_id: str
    exp24_parent_ref: str
    exp23_parent_ref: str
    steps: tuple[TraceStep, ...]


@dataclass(frozen=True)
class StructuralDifference:
    step_index: int
    left_digest: str
    right_digest: str
    reason: str


@dataclass(frozen=True)
class TraceComparison:
    identical: bool
    differences: tuple[StructuralDifference, ...]


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def payload_digest(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def stream_digest(stream: TraceStream) -> str:
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "agent_id": stream.agent_id,
        "exp24_parent_ref": stream.exp24_parent_ref,
        "exp23_parent_ref": stream.exp23_parent_ref,
        "steps": [
            {
                "step_index": step.step_index,
                "event_kind": step.event_kind,
                "payload_digest": step.payload_digest,
            }
            for step in stream.steps
        ],
    }
    return hashlib.sha256(_canonical_bytes(envelope)).hexdigest()


def validate_stream(stream: TraceStream) -> None:
    if not stream.exp24_parent_ref or not stream.exp23_parent_ref:
        raise ValueError("EXP-24 and EXP-23 lineage references are required")

    expected = list(range(len(stream.steps)))
    actual = [step.step_index for step in stream.steps]
    if actual != expected:
        raise ValueError("trace step sequence must be contiguous and ordered")


def compare_traces(left: TraceStream, right: TraceStream) -> TraceComparison:
    validate_stream(left)
    validate_stream(right)

    if (
        left.exp24_parent_ref != right.exp24_parent_ref
        or left.exp23_parent_ref != right.exp23_parent_ref
    ):
        raise ValueError("trace lineage references must match")

    differences: list[StructuralDifference] = []
    common_length = min(len(left.steps), len(right.steps))

    for index in range(common_length):
        left_step = left.steps[index]
        right_step = right.steps[index]
        if (
            left_step.step_index != right_step.step_index
            or left_step.event_kind != right_step.event_kind
            or left_step.payload_digest != right_step.payload_digest
        ):
            reason = (
                "payload_digest"
                if left_step.payload_digest != right_step.payload_digest
                else "step_structure"
            )
            differences.append(
                StructuralDifference(
                    step_index=index,
                    left_digest=left_step.payload_digest,
                    right_digest=right_step.payload_digest,
                    reason=reason,
                )
            )

    if len(left.steps) != len(right.steps):
        for index in range(common_length, max(len(left.steps), len(right.steps))):
            left_digest = left.steps[index].payload_digest if index < len(left.steps) else ""
            right_digest = right.steps[index].payload_digest if index < len(right.steps) else ""
            differences.append(
                StructuralDifference(
                    step_index=index,
                    left_digest=left_digest,
                    right_digest=right_digest,
                    reason="length",
                )
            )

    return TraceComparison(
        identical=not differences and stream_digest(left) == stream_digest(right),
        differences=tuple(differences),
    )
