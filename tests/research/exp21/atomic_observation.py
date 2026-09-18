"""Research-only atomic observation mapping for EXP-21."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = "exp21.observation.v0"


@dataclass(frozen=True)
class AtomicObservation:
    observation_id: str
    schema_version: str
    source_ref: str
    payload: dict[str, Any]
    immutable_hash: str


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def observation_digest(
    source_ref: str,
    payload: dict[str, Any],
    schema_version: str = SCHEMA_VERSION,
) -> str:
    envelope = {
        "schema_version": schema_version,
        "source_ref": source_ref,
        "payload": payload,
    }
    return hashlib.sha256(canonical_bytes(envelope)).hexdigest()


def from_text_record(record: dict[str, Any]) -> AtomicObservation:
    payload = {
        "source_type": record["source_type"],
        "normalized_text": record["normalized_text"],
        "metadata": dict(record["metadata"]),
        "provenance_hash": record["provenance_hash"],
    }
    digest = observation_digest(record["source_ref"], payload)
    return AtomicObservation(digest, SCHEMA_VERSION, record["source_ref"], payload, digest)


def from_transcript_record(record: dict[str, Any]) -> tuple[AtomicObservation, ...]:
    observations = []
    for index, segment in enumerate(record["segments"]):
        payload = {
            "source_type": record["source_type"],
            "segment_index": index,
            "start_ms": segment.start_ms,
            "end_ms": segment.end_ms,
            "text": segment.text,
            "provenance_hash": record["provenance_hash"],
        }
        digest = observation_digest(record["source_ref"], payload)
        observations.append(
            AtomicObservation(digest, SCHEMA_VERSION, record["source_ref"], payload, digest)
        )
    return tuple(observations)
