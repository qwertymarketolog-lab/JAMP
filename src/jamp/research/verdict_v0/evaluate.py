"""M1a evaluation facade. Closure authenticity and hermeticity are deferred to Stage D."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from jamp.research.specification_gate import GateResult, GateStatus, SpecificationRef
from jamp.research.verdict_v0.aggregation import (
    FROZEN_RULE,
    apply_standard_pass_fail_unknown_v0,
    is_frozen_rule,
)
from jamp.research.verdict_v0.schema import (
    CriterionResult,
    EvaluationRefusal,
    SpecGateResult,
    Verdict,
    compute_aggregation_rule_sha256,
    compute_claim_id,
    compute_gate_report_sha256,
    compute_verdict_id,
    is_valid_sha256,
)
from jamp.research.verdict_v0.stages import (
    NumericThresholdEvaluator,
    ScalarSelector,
    evaluate_criterion,
)

VERDICT_VERSION = "0.1.0"
EVALUATOR_VERSION = "0.1.0"
REFUSAL_VERSION = "0.1.0"
_ALLOWED_UNKNOWN = {"evidence_class_absent", "selector_unresolvable", "observed_inconclusive"}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _refuse(reason: str, detail: str | None = None) -> EvaluationRefusal:
    return EvaluationRefusal(REFUSAL_VERSION, reason, detail, _now())


def _criterion_set(value: Any) -> tuple[str, list[dict[str, Any]]] | EvaluationRefusal:
    if not isinstance(value, Mapping):
        return _refuse("CRITERION_SET_INVALID", "criterion_set must be a mapping")
    ref, criteria = value.get("criterion_set_ref"), value.get("criteria")
    if not is_valid_sha256(ref):
        return _refuse("CRITERION_SET_INVALID", "criterion_set_ref must be SHA-256")
    if not isinstance(criteria, list):
        return _refuse("CRITERION_SET_INVALID", "criteria must be an ordered list")
    refs, normalized = set(), []
    for index, item in enumerate(criteria):
        if not isinstance(item, Mapping):
            return _refuse("CRITERION_SET_INVALID", f"criterion[{index}] must be a mapping")
        criterion_ref = item.get("criterion_ref")
        if not is_valid_sha256(criterion_ref) or criterion_ref in refs:
            return _refuse(
                "CRITERION_SET_INVALID",
                f"criterion[{index}] reference invalid or duplicated",
            )
        if not isinstance(item.get("predicate"), Mapping):
            return _refuse("CRITERION_SET_INVALID", f"criterion[{index}] predicate invalid")
        if not isinstance(item.get("selector", "value"), str):
            return _refuse("CRITERION_SET_INVALID", f"criterion[{index}] selector invalid")
        refs.add(criterion_ref)
        normalized.append(dict(item))
    return ref, normalized


def evaluate(
    *,
    spec_ref: str,
    gate_result: GateResult,
    gate_sha256: str | None,
    selector_sha256: str | None,
    criterion_evaluator_sha256: str | None,
    aggregation_evaluator_sha256: str | None,
    criterion_set: dict[str, Any],
    evidence: dict[str, Any],
    rule: dict[str, Any],
) -> Verdict | EvaluationRefusal:
    closures = {
        "gate_sha256": gate_sha256,
        "selector_sha256": selector_sha256,
        "criterion_evaluator_sha256": criterion_evaluator_sha256,
        "aggregation_evaluator_sha256": aggregation_evaluator_sha256,
    }
    for name, value in closures.items():
        if not is_valid_sha256(value):
            return _refuse("CLOSURE_INCOMPLETE", f"{name} missing or malformed")
    assert (
        gate_sha256
        and selector_sha256
        and criterion_evaluator_sha256
        and aggregation_evaluator_sha256
    )

    if not isinstance(gate_result, GateResult) or not isinstance(
        gate_result.spec_ref, SpecificationRef
    ):
        return _refuse("GATE_RESULT_INVALID", "expected SpecificationGate GateResult")
    if not is_valid_sha256(spec_ref) or gate_result.spec_ref.spec_hash != spec_ref:
        return _refuse(
            "SPEC_REF_MISMATCH", "GateResult SpecificationRef hash differs from spec_ref"
        )
    if not isinstance(gate_result.status, GateStatus):
        return _refuse("GATE_STATUS_INVALID", "unrecognized GateStatus")
    if gate_result.status is GateStatus.UNKNOWN:
        return _refuse("GATE_UNKNOWN", "SpecificationGate returned GATE_UNKNOWN")
    spec_valid = gate_result.status is GateStatus.PASS
    if (spec_valid and gate_result.diagnostics) or (not spec_valid and not gate_result.diagnostics):
        return _refuse("GATE_RESULT_INVALID", "GateStatus and diagnostics are inconsistent")
    if not is_frozen_rule(rule):
        return _refuse("AGGREGATION_RULE_MISMATCH", "rule differs from frozen RC §7.2")
    if not isinstance(evidence, Mapping) or not is_valid_sha256(evidence.get("bundle_ref")):
        return _refuse("EVIDENCE_INVALID", "evidence mapping requires SHA-256 bundle_ref")
    checked = _criterion_set(criterion_set)
    if isinstance(checked, EvaluationRefusal):
        return checked
    criterion_set_ref, criteria = checked

    diagnostics = [{"code": d.code, "field": d.requirement} for d in gate_result.diagnostics]
    gate_version = gate_result.gate_contract_version
    gate_record = SpecGateResult(
        spec_ref,
        spec_valid,
        gate_version,
        gate_sha256,
        compute_gate_report_sha256(spec_ref, gate_sha256, gate_version, spec_valid, diagnostics),
    )
    selector, evaluator = ScalarSelector(), NumericThresholdEvaluator()
    results: list[CriterionResult] = []
    for criterion in criteria:
        item = evaluate_criterion(
            criterion,
            dict(evidence),
            selector,
            evaluator,
            selector_sha256=selector_sha256,
            evaluator_sha256=criterion_evaluator_sha256,
        )
        if item.unknown_reason not in _ALLOWED_UNKNOWN | {None}:
            return _refuse("CRITERION_RESULT_INVALID", "unknown_reason outside RC §5.6")
        results.append(item)
    expected = [item["criterion_ref"] for item in criteria]
    actual = [item.criterion_ref for item in results]
    if actual != expected or len(actual) != len(set(actual)):
        return _refuse("CRITERION_RESULTS_NOT_BIJECTIVE", "ordered Criterion Set bijection failed")

    status = apply_standard_pass_fail_unknown_v0(spec_valid, results)
    rule_sha = compute_aggregation_rule_sha256(FROZEN_RULE)
    base = {
        "verdict_version": VERDICT_VERSION,
        "verdict_status": status,
        "claim_id": compute_claim_id(spec_ref, criterion_set_ref),
        "spec_ref": spec_ref,
        "spec_gate_result": gate_record,
        "criterion_set_ref": criterion_set_ref,
        "evidence_bundle_ref": evidence["bundle_ref"],
        "aggregation_rule_id": FROZEN_RULE["rule_id"],
        "aggregation_rule_version": FROZEN_RULE["rule_version"],
        "aggregation_rule_sha256": rule_sha,
        "evaluator_version": EVALUATOR_VERSION,
        "evaluator_sha256": aggregation_evaluator_sha256,
        "criterion_results": tuple(results),
        "created_at": _now(),
        "verdict_id": "",
        "rule_package_sha256": None,
    }
    base["verdict_id"] = compute_verdict_id(Verdict(**base))
    return Verdict(**base)
