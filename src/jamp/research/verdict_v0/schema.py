"""Verdict v0 schema and RC v0.4 identity projections; distinct from runtime JampVerdict."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from jamp.research.canonical import canonical_bytes

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
DOMAIN_VERDICT = b"jamp:verdict:v0:"
DOMAIN_CLAIM = b"jamp:claim:v0:"
DOMAIN_GATE = b"jamp:gate-report:v0:"
DOMAIN_RULE = b"jamp:aggregation-rule:v0:"


def is_valid_sha256(value: str | None) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


class VerdictStatus(str, Enum):  # noqa: UP042
    VERIFIED = "VERIFIED"
    CONTRADICTED = "CONTRADICTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    REFUSE = "REFUSE"


CriterionResultValue = Literal["PASS", "FAIL", "UNKNOWN"]


@dataclass(frozen=True, slots=True)
class SpecGateResult:
    spec_ref: str
    spec_valid: bool
    gate_version: str
    gate_sha256: str
    gate_report_sha256: str


def compute_gate_report_sha256(
    spec_ref: str,
    gate_sha256: str,
    gate_version: str,
    spec_valid: bool,
    diagnostics: list[dict[str, Any]],
) -> str:
    def key(item: dict[str, Any]) -> tuple[str, tuple[int, str]]:
        field = item.get("field")
        return str(item["code"]), ((1, "") if field is None else (0, str(field)))

    projection = {
        "spec_ref": spec_ref,
        "gate_sha256": gate_sha256,
        "gate_version": gate_version,
        "spec_valid": spec_valid,
        "diagnostics": sorted(diagnostics, key=key),
    }
    return hashlib.sha256(DOMAIN_GATE + canonical_bytes(projection)).hexdigest()


@dataclass(frozen=True, slots=True)
class EvaluationTrace:
    criterion_evaluator_sha256: str
    evidence_selector_sha256: str
    selector_output: dict[str, Any]
    predicate_result: bool | Literal["unknown"]


@dataclass(frozen=True, slots=True)
class CriterionResult:
    criterion_ref: str
    result: CriterionResultValue
    evaluation_trace: EvaluationTrace
    unknown_reason: str | None
    reasoning: str | None = None


@dataclass(frozen=True, slots=True)
class Verdict:
    verdict_version: str
    verdict_status: VerdictStatus
    claim_id: str
    spec_ref: str
    spec_gate_result: SpecGateResult
    criterion_set_ref: str
    evidence_bundle_ref: str
    aggregation_rule_id: str
    aggregation_rule_version: str
    aggregation_rule_sha256: str
    evaluator_version: str
    evaluator_sha256: str
    criterion_results: tuple[CriterionResult, ...]
    created_at: str
    verdict_id: str
    rule_package_sha256: str | None = None


def compute_verdict_id(v: Verdict) -> str:
    projection = {
        "verdict_version": v.verdict_version,
        "verdict_status": v.verdict_status.value,
        "claim_id": v.claim_id,
        "spec_ref": v.spec_ref,
        "spec_gate_result": {
            "spec_ref": v.spec_gate_result.spec_ref,
            "spec_valid": v.spec_gate_result.spec_valid,
            "gate_version": v.spec_gate_result.gate_version,
            "gate_sha256": v.spec_gate_result.gate_sha256,
            "gate_report_sha256": v.spec_gate_result.gate_report_sha256,
        },
        "criterion_set_ref": v.criterion_set_ref,
        "evidence_bundle_ref": v.evidence_bundle_ref,
        "aggregation_rule_id": v.aggregation_rule_id,
        "aggregation_rule_version": v.aggregation_rule_version,
        "aggregation_rule_sha256": v.aggregation_rule_sha256,
        "evaluator_version": v.evaluator_version,
        "evaluator_sha256": v.evaluator_sha256,
        "criterion_results": [
            {
                "criterion_ref": r.criterion_ref,
                "result": r.result,
                "evaluation_trace": {
                    "criterion_evaluator_sha256": r.evaluation_trace.criterion_evaluator_sha256,
                    "evidence_selector_sha256": r.evaluation_trace.evidence_selector_sha256,
                    "selector_output": r.evaluation_trace.selector_output,
                    "predicate_result": r.evaluation_trace.predicate_result,
                },
                "unknown_reason": r.unknown_reason,
            }
            for r in v.criterion_results
        ],
    }
    return hashlib.sha256(DOMAIN_VERDICT + canonical_bytes(projection)).hexdigest()


def compute_claim_id(spec_ref: str, criterion_set_ref: str) -> str:
    return hashlib.sha256(
        DOMAIN_CLAIM
        + canonical_bytes({"spec_ref": spec_ref, "criterion_set_ref": criterion_set_ref})
    ).hexdigest()


def compute_aggregation_rule_sha256(rule: dict[str, Any]) -> str:
    procedure = rule["decision_procedure"]
    projection = {
        "rule_id": rule["rule_id"],
        "rule_version": rule["rule_version"],
        "preconditions": rule["preconditions"],
        "decision_procedure": procedure,
        "decision_procedure_sha256": hashlib.sha256(canonical_bytes(procedure)).hexdigest(),
    }
    return hashlib.sha256(DOMAIN_RULE + canonical_bytes(projection)).hexdigest()


@dataclass(frozen=True, slots=True)
class EvaluationRefusal:
    """Structural refusal; RC §14 does not define its ID projection."""

    refusal_version: str
    refusal_reason: str
    refusal_detail: str | None
    created_at: str
    refusal_id: None = None
