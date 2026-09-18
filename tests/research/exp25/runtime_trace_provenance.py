"""Research-only runtime trace provenance for EXP-25.

This module models deterministic fixture event streams only. It records
sequence/provenance metadata and never assigns semantic outcomes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = "exp25.runtime_trace_provenance.v0"
SEMANTIC_KEYS = frozenset({"goal_met", "error_bad", "policy_violated"})


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


@dataclass(frozen=True)
class TraceEvent:
    step_index: int
    event_kind: str
    payload_digest: str


@dataclass(frozen=True)
class RuntimeTraceObservation:
    trace_id: str
    schema_version: str
    exp24_parent_ref: str
    exp23_parent_ref: str
    events: tuple[TraceEvent, ...]
    cumulative_digest: str


def payload_digest(payload: Any) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _trace_digest(
    *,
    exp24_parent_ref: str,
    exp23_parent_ref: str,
    events: tuple[TraceEvent, ...],
    schema_version: str = SCHEMA_VERSION,
) -> str:
    envelope = {
        "schema_version": schema_version,
        "exp24_parent_ref": exp24_parent_ref,
        "exp23_parent_ref": exp23_parent_ref,
        "events": [
            {
                "step_index": event.step_index,
                "event_kind": event.event_kind,
                "payload_digest": event.payload_digest,
            }
            for event in events
        ],
    }
    return hashlib.sha256(canonical_bytes(envelope)).hexdigest()


def build_runtime_trace_observation(
    record: dict[str, Any],
) -> RuntimeTraceObservation:
    if not record.get("exp24_parent_ref") or not record.get("exp23_parent_ref"):
        raise ValueError("EXP-24 and EXP-23 parent references are required")

    raw_events = record.get("events", [])
    events = tuple(
        TraceEvent(
            step_index=int(item["step_index"]),
            event_kind=str(item["event_kind"]),
            payload_digest=str(item["payload_digest"]),
        )
        for item in raw_events
    )
    expected = list(range(len(events)))
    actual = [event.step_index for event in events]
    if actual != expected:
        raise ValueError("trace step sequence must be contiguous and ordered")

    digest = _trace_digest(
        exp24_parent_ref=record["exp24_parent_ref"],
        exp23_parent_ref=record["exp23_parent_ref"],
        events=events,
    )
    return RuntimeTraceObservation(
        trace_id=digest,
        schema_version=SCHEMA_VERSION,
        exp24_parent_ref=record["exp24_parent_ref"],
        exp23_parent_ref=record["exp23_parent_ref"],
        events=events,
        cumulative_digest=digest,
    )
