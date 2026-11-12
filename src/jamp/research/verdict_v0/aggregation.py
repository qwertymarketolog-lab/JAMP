"""Frozen standard-pass-fail-unknown aggregation (RC §7)."""

from __future__ import annotations

from typing import Any

from jamp.research.canonical import canonical_bytes
from jamp.research.verdict_v0.schema import CriterionResult, VerdictStatus


class EvaluationError(Exception):
    """RC §3 evaluator invariant violation."""


FROZEN_RULE: dict[str, Any] = {
    "rule_id": "standard-pass-fail-unknown",
    "rule_version": "0.1.0",
    "preconditions": {
        "input_structure_valid": True,
        "spec_ref_resolves": True,
        "criterion_set_frozen": True,
        "criterion_results_bijection": True,
        "spec_gate_result_verifiable": True,
    },
    "decision_procedure": [
        {"if": "spec_valid == false", "return": "REFUSE"},
        {"if": "true ∧ criterion_count == 0", "return": "REFUSE"},
        {"if": "true ∧ any(result == FAIL)", "return": "CONTRADICTED"},
        {"if": "true ∧ any(result == UNKNOWN)", "return": "INCONCLUSIVE"},
        {"if": "true ∧ all(result == PASS)", "return": "VERIFIED"},
    ],
}


def is_frozen_rule(rule: Any) -> bool:
    if not isinstance(rule, dict):
        return False
    try:
        return canonical_bytes(rule) == canonical_bytes(FROZEN_RULE)
    except (TypeError, ValueError):
        return False


def apply_standard_pass_fail_unknown_v0(
    spec_valid: bool, results: list[CriterionResult] | tuple[CriterionResult, ...]
) -> VerdictStatus:
    if not spec_valid:
        return VerdictStatus.REFUSE
    if not results:
        return VerdictStatus.REFUSE
    values = [item.result for item in results]
    if any(value not in {"PASS", "FAIL", "UNKNOWN"} for value in values):
        raise EvaluationError("criterion result outside frozen vocabulary")
    if "FAIL" in values:
        return VerdictStatus.CONTRADICTED
    if "UNKNOWN" in values:
        return VerdictStatus.INCONCLUSIVE
    if all(value == "PASS" for value in values):
        return VerdictStatus.VERIFIED
    raise EvaluationError("standard-pass-fail-unknown-v0: no class matched")
