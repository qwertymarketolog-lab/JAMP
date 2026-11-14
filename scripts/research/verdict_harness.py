"""Offline, fail-closed validation for JAMP Audit v1 model claims.

This module never performs network I/O and never acts as an LLM judge.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "docs/experiments/jamp_audit_v1"
CLAIM_STATUSES = frozenset({
    "OBSERVED", "INFERRED", "UNKNOWN", "VERIFICATION_CANDIDATE", "VERIFIED", "AMBIGUOUS",
})
INPUT_PATHS = (
    "docs/experiments/jamp_audit_v1/AUDIT_PROMPT.md",
    "docs/experiments/jamp_audit_v1/INPUT_PACK.md",
)


def sha256_bytes(data: bytes) -> str:
    """Return SHA-256 of exact bytes without normalization."""
    return hashlib.sha256(data).hexdigest()


def hash_input_files(root: Path = ROOT) -> dict[str, str]:
    """Hash the exact committed input bytes."""
    return {path: sha256_bytes((root / path).read_bytes()) for path in INPUT_PATHS}


def hash_response_body(
    response_body_bytes: bytes, *, encoding: str = "utf-8"
) -> dict[str, str | None]:
    """Hash decoded HTTP entity-body bytes and strict-decoded text separately."""
    body_hash = sha256_bytes(response_body_bytes)
    try:
        response_text = response_body_bytes.decode(encoding, errors="strict")
    except (LookupError, UnicodeDecodeError):
        return {
            "response_body_bytes_sha256": body_hash,
            "response_text_sha256": None,
            "reason": "RESPONSE_TEXT_DECODE_ERROR",
        }
    return {
        "response_body_bytes_sha256": body_hash,
        "response_text_sha256": sha256_bytes(response_text.encode("utf-8")),
        "reason": None,
    }


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def validate_schema_instance(value: Any, schema: dict[str, Any], path: str = "$") -> None:
    """Validate the JSON Schema subset used by the checked-in contracts."""
    expected_type = schema.get("type")
    if expected_type and not _matches_type(value, expected_type):
        raise ValueError(f"{path}: expected {expected_type}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path}: value is outside enum")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            raise ValueError(f"{path}: string is too short")
        pattern = schema.get("pattern")
        if pattern and re.fullmatch(pattern, value) is None:
            raise ValueError(f"{path}: string does not match pattern")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ValueError(f"{path}: array is too short")
        if schema.get("uniqueItems") and len(value) != len(set(value)):
            raise ValueError(f"{path}: array items are not unique")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                validate_schema_instance(item, item_schema, f"{path}[{index}]")
    if isinstance(value, dict):
        missing = sorted(set(schema.get("required", [])) - set(value))
        if missing:
            raise ValueError(f"{path}: missing required fields {missing}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                raise ValueError(f"{path}: additional properties {extra}")
        for key, item in value.items():
            if key in properties:
                validate_schema_instance(item, properties[key], f"{path}.{key}")


def _load_schema(filename: str) -> dict[str, Any]:
    value = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Schema {filename} must be an object")
    return value


def parse_model_response(
    response_body_bytes: bytes, *, encoding: str = "utf-8"
) -> dict[str, Any]:
    """Parse raw JSON only; fenced Markdown and malformed claims fail closed."""
    hashes = hash_response_body(response_body_bytes, encoding=encoding)
    if hashes["response_text_sha256"] is None:
        return {"status": "UNKNOWN", "reason": hashes["reason"], "payload": None, **hashes}
    try:
        response_text = response_body_bytes.decode(encoding, errors="strict")
        payload = json.loads(response_text)
    except (LookupError, UnicodeDecodeError, json.JSONDecodeError):
        return {
            "status": "UNKNOWN",
            "reason": "MALFORMED_RESPONSE",
            "payload": None,
            **hashes,
        }
    try:
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != "1.0"
            or not isinstance(payload.get("model_id"), str)
            or not payload["model_id"]
            or not isinstance(payload.get("task_answers"), dict)
            or not isinstance(payload.get("claims"), list)
        ):
            raise ValueError("Invalid top-level response shape")
        task_answers = payload["task_answers"]
        if not {"work_assessment", "improvement_opportunities", "six_month_plan"} <= set(task_answers):
            raise ValueError("Missing task answer")
        plan = task_answers["six_month_plan"]
        if not isinstance(plan, dict) or not {"NOW", "NEXT", "LATER"} <= set(plan):
            raise ValueError("Invalid six-month plan")
        claim_schema = _load_schema("claim.schema.json")
        for claim in payload["claims"]:
            validate_schema_instance(claim, claim_schema, "$response.claims")
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return {
            "status": "UNKNOWN",
            "reason": "MALFORMED_RESPONSE",
            "payload": None,
            **hashes,
        }
    return {"status": "OBSERVED", "reason": None, "payload": payload, **hashes}


def validate_evidence_records(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    schema = _load_schema("evidence.schema.json")
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        validate_schema_instance(record, schema, "$evidence")
        evidence_id = record["evidence_id"]
        if evidence_id in indexed:
            raise ValueError(f"Duplicate evidence_id: {evidence_id}")
        indexed[evidence_id] = record
    return indexed


def validate_resolution(
    resolution: dict[str, Any], *, claim_id: str, evidence_by_id: dict[str, dict[str, Any]]
) -> None:
    schema = _load_schema("resolution.schema.json")
    validate_schema_instance(resolution, schema, "$resolution")
    if resolution["claim_id"] != claim_id:
        raise ValueError("Human resolution claim_id mismatch")
    missing = set(resolution["evidence_ids"]) - set(evidence_by_id)
    if missing:
        raise ValueError(f"Human resolution references unknown evidence: {sorted(missing)}")
    if resolution["decision"] == "VERIFIED" and not resolution["evidence_ids"]:
        raise ValueError("VERIFIED human resolution requires evidence")


def validate_claim(
    claim: dict[str, Any],
    evidence_records: list[dict[str, Any]],
    resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a claim; model VERIFIED becomes a candidate until human resolution."""
    schema = _load_schema("claim.schema.json")
    validate_schema_instance(claim, schema, "$claim")
    if claim["status"] not in CLAIM_STATUSES:
        raise ValueError("Unsupported claim status")
    evidence_by_id = validate_evidence_records(evidence_records)
    evidence_ids = set(claim["evidence_ids"])
    missing = evidence_ids - set(evidence_by_id)
    if missing:
        raise ValueError(f"Claim references unknown evidence: {sorted(missing)}")
    result = dict(claim)
    if result["status"] in {"VERIFIED", "VERIFICATION_CANDIDATE"}:
        if not evidence_ids:
            raise ValueError(f"{result['status']} requires at least one evidence_id")
        if resolution is None:
            result["status"] = "VERIFICATION_CANDIDATE"
            return result
        validate_resolution(resolution, claim_id=result["claim_id"], evidence_by_id=evidence_by_id)
        if resolution["decision"] == "VERIFIED":
            if not evidence_ids.issubset(set(resolution["evidence_ids"])):
                raise ValueError("Human resolution does not cover every claim evidence_id")
            result["status"] = "VERIFIED"
        else:
            result["status"] = resolution["decision"]
    elif result["status"] == "AMBIGUOUS" and resolution is None:
        raise ValueError("AMBIGUOUS claim requires an explicit human resolution")
    elif resolution is not None:
        validate_resolution(resolution, claim_id=result["claim_id"], evidence_by_id=evidence_by_id)
        result["status"] = resolution["decision"]
    return result


def create_ambiguous_conflict(
    *,
    conflict_id: str,
    conflict_type: str,
    claim_id: str,
    human_matched: bool,
    participants: list[dict[str, str]],
    evidence_id: str | None = None,
    evidence_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a conflict only after a human explicitly matched the contradiction."""
    if not human_matched:
        raise ValueError("Human matching is required; semantic matching is out of scope")
    if not conflict_id or not claim_id:
        raise ValueError("conflict_id and claim_id are required")
    if conflict_type == "claim_vs_claim":
        if len(participants) != 2 or any(
            not item.get("model") or not item.get("claim") for item in participants
        ):
            raise ValueError("claim_vs_claim requires two model/claim participants")
    elif conflict_type == "claim_vs_evidence":
        if len(participants) != 1 or not evidence_id:
            raise ValueError("claim_vs_evidence requires one claim participant and evidence_id")
        evidence_by_id = validate_evidence_records(evidence_records or [])
        if evidence_id not in evidence_by_id:
            raise ValueError("claim_vs_evidence references unknown evidence")
    else:
        raise ValueError("Unsupported conflict_type")
    return {
        "conflict_id": conflict_id,
        "claim_id": claim_id,
        "conflict_type": conflict_type,
        "status": "AMBIGUOUS",
        "participants": participants,
        "evidence_id": evidence_id,
        "resolution": None,
        "resolved_by": None,
    }
