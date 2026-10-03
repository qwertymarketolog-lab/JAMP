"""Deterministic Evidence Acquisition v0 checker."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

CHECKER_ID = "http-json-repo-checker"
CHECKER_VERSION = "1"
INPUT_SCHEMA_VERSION = "raw-output-v1"
CANONICALIZATION_RULES = "json-sort-keys-separators-utf8"
CHECKER_CONTRACT = {
    "checker_id": CHECKER_ID,
    "checker_version": CHECKER_VERSION,
    "input_schema_version": INPUT_SCHEMA_VERSION,
    "canonicalization_rules": CANONICALIZATION_RULES,
    "required_input_digests": ["raw_response_digest"],
    "output_schema": {
        "checker_id": "string",
        "checker_version": "string",
        "input_digest": "sha256",
        "accepted": "boolean",
        "status": "CHECKED|FAILED|INCONCLUSIVE",
        "reason": "string",
    },
    "acceptance_predicate": "HTTP 200 JSON full_name equals qwertymarketolog-lab/JAMP",
    "rejection_predicate": "HTTP 200 valid JSON repository identity mismatch",
    "inconclusive_predicate": "missing transport status or required JSON evidence",
    "self_test_fixtures": [
        {
            "http_status": 200,
            "body": {"full_name": "qwertymarketolog-lab/JAMP"},
            "status": "CHECKED",
        },
        {
            "http_status": 200,
            "body": {"full_name": "other/repository"},
            "status": "FAILED",
        },
        {"http_status": None, "body": None, "status": "INCONCLUSIVE"},
    ],
}


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def checker_digest() -> str:
    return hashlib.sha256(_canonical(CHECKER_CONTRACT)).hexdigest()


@dataclass(frozen=True)
class CheckerResult:
    checker_id: str
    checker_version: str
    input_digest: str
    accepted: bool
    status: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def check(
    *,
    raw_response: bytes,
    raw_response_digest: str,
    http_status: int | None,
) -> CheckerResult:
    if hashlib.sha256(raw_response).hexdigest() != raw_response_digest:
        return CheckerResult(
            CHECKER_ID,
            CHECKER_VERSION,
            raw_response_digest,
            False,
            "INCONCLUSIVE",
            "raw_response_digest_mismatch",
        )
    if http_status is None:
        return CheckerResult(
            CHECKER_ID,
            CHECKER_VERSION,
            raw_response_digest,
            False,
            "INCONCLUSIVE",
            "missing_transport_status",
        )
    try:
        payload = json.loads(raw_response)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return CheckerResult(
            CHECKER_ID,
            CHECKER_VERSION,
            raw_response_digest,
            False,
            "INCONCLUSIVE",
            "required_json_evidence_unavailable",
        )
    if not isinstance(payload, dict):
        return CheckerResult(
            CHECKER_ID,
            CHECKER_VERSION,
            raw_response_digest,
            False,
            "INCONCLUSIVE",
            "required_json_object_unavailable",
        )
    if http_status == 200 and payload.get("full_name") == "qwertymarketolog-lab/JAMP":
        return CheckerResult(
            CHECKER_ID,
            CHECKER_VERSION,
            raw_response_digest,
            True,
            "CHECKED",
            "repository_identity_match",
        )
    return CheckerResult(
        CHECKER_ID,
        CHECKER_VERSION,
        raw_response_digest,
        False,
        "FAILED",
        "repository_identity_mismatch",
    )


def replay_check(
    *,
    raw_response: bytes,
    raw_response_digest: str,
    http_status: int | None,
    declared_checker_version: str,
) -> dict[str, Any]:
    if declared_checker_version != CHECKER_VERSION:
        return {
            "status": "REPLAY_INCONCLUSIVE",
            "reason": "version mismatch",
            "checker_id": CHECKER_ID,
            "checker_version": declared_checker_version,
        }
    return check(
        raw_response=raw_response,
        raw_response_digest=raw_response_digest,
        http_status=http_status,
    ).as_dict()
