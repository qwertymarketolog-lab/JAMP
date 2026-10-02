"""Fail-closed deterministic Conflict Record primitives for JAMP-AI-HARDWARE-v0.1.4."""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

PREFIX = "sha256:"
CONTRACT_VERSION = "JAMP-AI-HARDWARE-v0.1.4"


def _finite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite JSON number")
    if isinstance(value, Mapping):
        for item in value.values():
            _finite(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _finite(item)


def canonical_timestamp(value: str) -> str:
    """Normalize RFC3339 input to UTC with exactly six fractional digits."""
    if not isinstance(value, str):
        raise TypeError("timestamp must be a string")
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    parsed = parsed.astimezone(UTC)
    return parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def canonical_json(value: Any) -> bytes:
    """JAMP C14N-v0.1.4: UTF-8, sorted object keys, preserved arrays, no NaN."""
    _finite(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(evidence)
    result["timestamp"] = canonical_timestamp(str(result["timestamp"]))
    return result


def conflict_material(record: Mapping[str, Any]) -> dict[str, Any]:
    if record.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("unsupported contract version")
    if "conflict_id" in record:
        record = {key: value for key, value in record.items() if key != "conflict_id"}
    a = _canonical_evidence(record["evidence_a"])
    b = _canonical_evidence(record["evidence_b"])
    a, b = sorted((a, b), key=lambda item: item["artifact_sha256"])
    material = dict(record)
    material["evidence_a"] = a
    material["evidence_b"] = b
    return material


def calculate_conflict_id(record: Mapping[str, Any]) -> str:
    return PREFIX + hashlib.sha256(canonical_json(conflict_material(record))).hexdigest()


def verify_conflict_id(record: Mapping[str, Any]) -> bool:
    return record.get("conflict_id") == calculate_conflict_id(record)


def same_scope(record_a: Mapping[str, Any], record_b: Mapping[str, Any]) -> bool:
    return record_a.get("subject_identity") == record_b.get("subject_identity")


def classify_scope(record_a: Mapping[str, Any], record_b: Mapping[str, Any]) -> str:
    return "SAME_SCOPE" if same_scope(record_a, record_b) else "DIFFERENT_SCOPE"


def is_duplicate_evidence(
    evidence_a: Mapping[str, Any], evidence_b: Mapping[str, Any]
) -> bool:
    return evidence_a.get("artifact_sha256") == evidence_b.get("artifact_sha256")


def build_conflict_record(
    *,
    predicate_id: str,
    conflict_type: str,
    subject_identity: Mapping[str, Any],
    evidence_a: Mapping[str, Any],
    evidence_b: Mapping[str, Any],
    observed_a: Any,
    observed_b: Any,
) -> dict[str, Any]:
    if is_duplicate_evidence(evidence_a, evidence_b):
        raise ValueError("duplicate evidence cannot form a conflict")
    if observed_a == observed_b:
        raise ValueError("equal observations cannot form a conflict")
    record = {
        "contract_version": CONTRACT_VERSION,
        "conflict_id": "",
        "predicate_id": predicate_id,
        "conflict_type": conflict_type,
        "subject_identity": dict(subject_identity),
        "evidence_a": dict(evidence_a),
        "evidence_b": dict(evidence_b),
        "observed_values": {"a": observed_a, "b": observed_b},
    }
    record["conflict_id"] = calculate_conflict_id(record)
    return record
