"""Research-only AI/harness observation engine for EXP-23.

This module records observable execution context and results without assigning
semantic verdicts. It is deliberately isolated from src/jamp.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = "exp23.ai_harness_observation.v0"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


@dataclass(frozen=True)
class HarnessSpec:
    harness_id: str
    harness_version: str
    tools: tuple[str, ...]
    policy: str


@dataclass(frozen=True)
class AIObservation:
    observation_id: str
    schema_version: str
    source_ref: str
    model_id: str
    model_version: str
    harness: HarnessSpec
    attempt_index: int
    input_payload: dict[str, Any]
    output_payload: dict[str, Any]
    provenance: dict[str, Any]
    immutable_hash: str


def observation_digest(
    *,
    source_ref: str,
    model_id: str,
    model_version: str,
    harness: HarnessSpec,
    attempt_index: int,
    input_payload: dict[str, Any],
    output_payload: dict[str, Any],
    provenance: dict[str, Any],
    schema_version: str = SCHEMA_VERSION,
) -> str:
    envelope = {
        "schema_version": schema_version,
        "source_ref": source_ref,
        "model_id": model_id,
        "model_version": model_version,
        "harness": {
            "harness_id": harness.harness_id,
            "harness_version": harness.harness_version,
            "tools": list(harness.tools),
            "policy": harness.policy,
        },
        "attempt_index": attempt_index,
        "input_payload": input_payload,
        "output_payload": output_payload,
        "provenance": provenance,
    }
    return hashlib.sha256(canonical_bytes(envelope)).hexdigest()


def build_observation(record: dict[str, Any]) -> AIObservation:
    harness_record = record["harness"]
    harness = HarnessSpec(
        harness_id=harness_record["harness_id"],
        harness_version=harness_record["harness_version"],
        tools=tuple(harness_record["tools"]),
        policy=harness_record["policy"],
    )
    digest = observation_digest(
        source_ref=record["source_ref"],
        model_id=record["model_id"],
        model_version=record["model_version"],
        harness=harness,
        attempt_index=record["attempt_index"],
        input_payload=dict(record["input_payload"]),
        output_payload=dict(record["output_payload"]),
        provenance=dict(record["provenance"]),
    )
    return AIObservation(
        observation_id=digest,
        schema_version=SCHEMA_VERSION,
        source_ref=record["source_ref"],
        model_id=record["model_id"],
        model_version=record["model_version"],
        harness=harness,
        attempt_index=record["attempt_index"],
        input_payload=dict(record["input_payload"]),
        output_payload=dict(record["output_payload"]),
        provenance=dict(record["provenance"]),
        immutable_hash=digest,
    )
