"""M1a contract tests use the repository's actual GateResult dataclass."""

from __future__ import annotations

from typing import Any

import pytest

from jamp.research.specification_gate import (
    Diagnostic,
    GateResult,
    GateStatus,
    SpecificationRef,
)
from jamp.research.verdict_v0.aggregation import (
    FROZEN_RULE,
    EvaluationError,
    apply_standard_pass_fail_unknown_v0,
    is_frozen_rule,
)
from jamp.research.verdict_v0.evaluate import evaluate
from jamp.research.verdict_v0.schema import (
    CriterionResult,
    EvaluationRefusal,
    EvaluationTrace,
    Verdict,
    VerdictStatus,
)

A, B, C, D = ("a" * 64, "b" * 64, "c" * 64, "d" * 64)
SPEC, SET, BUNDLE = "1" * 64, "2" * 64, "3" * 64


def _gate(status: GateStatus = GateStatus.PASS) -> GateResult:
    diagnostics = (
        (Diagnostic("SCHEMA_VIOLATION", SPEC, "scope", "invalid"),)
        if status is GateStatus.FAIL
        else ()
    )
    return GateResult(status, SpecificationRef("spec-1", "1.0.0", SPEC), (SPEC,), diagnostics, "v0")


def _criteria(count: int = 1, threshold: Any = 5.0) -> dict[str, Any]:
    return {
        "criterion_set_ref": SET,
        "criteria": [
            {
                "criterion_ref": f"{i + 10:064x}",
                "selector": "value",
                "predicate": {"op": ">=", "threshold": threshold},
            }
            for i in range(count)
        ],
    }


def _evidence(value: Any = 10.0) -> dict[str, Any]:
    return {"class": "scalar", "value": value, "bundle_ref": BUNDLE}


def _rule() -> dict[str, Any]:
    return {
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


def _call(**updates: Any) -> Verdict | EvaluationRefusal:
    args = {
        "spec_ref": SPEC,
        "gate_result": _gate(),
        "gate_sha256": A,
        "selector_sha256": B,
        "criterion_evaluator_sha256": C,
        "aggregation_evaluator_sha256": D,
        "criterion_set": _criteria(),
        "evidence": _evidence(),
        "rule": _rule(),
    }
    args.update(updates)
    return evaluate(**args)


def test_class_a_invalid_spec_refuse():
    result = _call(gate_result=_gate(GateStatus.FAIL))
    assert isinstance(result, Verdict) and result.verdict_status is VerdictStatus.REFUSE


def test_class_b_empty_criterion_set_refuse():
    result = _call(criterion_set=_criteria(0))
    assert isinstance(result, Verdict) and result.verdict_status is VerdictStatus.REFUSE


def test_class_c_fail_contradicted():
    result = _call(criterion_set=_criteria(threshold=100))
    assert isinstance(result, Verdict) and result.verdict_status is VerdictStatus.CONTRADICTED


def test_class_d_unknown_inconclusive():
    result = _call(evidence=_evidence("not-numeric"))
    assert isinstance(result, Verdict) and result.verdict_status is VerdictStatus.INCONCLUSIVE


def test_class_e_pass_verified():
    result = _call()
    assert isinstance(result, Verdict) and result.verdict_status is VerdictStatus.VERIFIED


def test_pass_plus_unknown_inconclusive():
    cs = _criteria(2)
    cs["criteria"][1]["predicate"]["threshold"] = "bad"
    result = _call(criterion_set=cs)
    assert isinstance(result, Verdict)
    assert [x.result for x in result.criterion_results] == ["PASS", "UNKNOWN"]
    assert result.verdict_status is VerdictStatus.INCONCLUSIVE


def test_fail_plus_unknown_contradicted():
    cs = _criteria(2, 100)
    cs["criteria"][1]["predicate"]["threshold"] = "bad"
    result = _call(criterion_set=cs)
    assert isinstance(result, Verdict)
    assert [x.result for x in result.criterion_results] == ["FAIL", "UNKNOWN"]
    assert result.verdict_status is VerdictStatus.CONTRADICTED


def test_gate_unknown_returns_refusal():
    result = _call(gate_result=_gate(GateStatus.UNKNOWN))
    assert isinstance(result, EvaluationRefusal) and result.refusal_reason == "GATE_UNKNOWN"
    assert not hasattr(result, "verdict_status")


def test_unknown_gate_status_refuses():
    gate = GateResult("GATE_MAYBE", SpecificationRef("spec-1", "1.0.0", SPEC), (), ())  # type: ignore[arg-type]
    result = _call(gate_result=gate)
    assert isinstance(result, EvaluationRefusal) and result.refusal_reason == "GATE_STATUS_INVALID"


def test_gate_spec_ref_mismatch_refuses():
    gate = GateResult(GateStatus.PASS, SpecificationRef("other", "1.0.0", "9" * 64), (), ())
    result = _call(gate_result=gate)
    assert isinstance(result, EvaluationRefusal)
    assert result.refusal_reason == "SPEC_REF_MISMATCH"


@pytest.mark.parametrize(
    "param",
    [
        "gate_sha256",
        "selector_sha256",
        "criterion_evaluator_sha256",
        "aggregation_evaluator_sha256",
    ],
)
def test_each_missing_closure_refuses(param):
    result = _call(**{param: None})
    assert isinstance(result, EvaluationRefusal)
    assert result.refusal_reason == "CLOSURE_INCOMPLETE" and param in (result.refusal_detail or "")


@pytest.mark.parametrize("bad", ["", "unknown", "A" * 64, "a" * 63, "a" * 65, "z" * 64])
def test_bad_closure_format_refuses(bad):
    assert isinstance(_call(gate_sha256=bad), EvaluationRefusal)


def test_production_defaults_fail_closed():
    result = _call(
        gate_sha256=None,
        selector_sha256=None,
        criterion_evaluator_sha256=None,
        aggregation_evaluator_sha256=None,
    )
    assert isinstance(result, EvaluationRefusal)


def test_duplicate_criterion_refs_refuse():
    cs = _criteria(2)
    cs["criteria"][1]["criterion_ref"] = cs["criteria"][0]["criterion_ref"]
    result = _call(criterion_set=cs)
    assert isinstance(result, EvaluationRefusal)
    assert result.refusal_reason == "CRITERION_SET_INVALID"


def test_invalid_criterion_ref_refuses():
    cs = _criteria()
    cs["criteria"][0]["criterion_ref"] = "bad"
    assert isinstance(_call(criterion_set=cs), EvaluationRefusal)


def test_criterion_result_order_matches_set():
    result = _call(criterion_set=_criteria(3))
    assert isinstance(result, Verdict)
    expected = [item["criterion_ref"] for item in _criteria(3)["criteria"]]
    assert [item.criterion_ref for item in result.criterion_results] == expected


def test_non_list_criteria_refuses():
    assert isinstance(
        _call(criterion_set={"criterion_set_ref": SET, "criteria": "bad"}),
        EvaluationRefusal,
    )


def test_bad_bundle_ref_refuses():
    assert isinstance(
        _call(evidence={"class": "scalar", "value": 1, "bundle_ref": "bad"}),
        EvaluationRefusal,
    )


def test_rule_version_tampering_refuses():
    rule = _rule()
    rule["rule_version"] = "0.1.1"
    result = _call(rule=rule)
    assert isinstance(result, EvaluationRefusal)
    assert result.refusal_reason == "AGGREGATION_RULE_MISMATCH"


def test_rule_clause_order_tampering_refuses():
    rule = _rule()
    rule["decision_procedure"].reverse()
    assert not is_frozen_rule(rule)
    assert isinstance(_call(rule=rule), EvaluationRefusal)


def test_selector_unknown_reason_is_exact_rc_value():
    cs = _criteria()
    cs["criteria"][0]["selector"] = "missing"
    result = _call(criterion_set=cs)
    assert isinstance(result, Verdict)
    assert result.criterion_results[0].unknown_reason == "selector_unresolvable"


def test_absent_evidence_class_uses_rc_value():
    result = _call(evidence={"bundle_ref": BUNDLE})
    assert isinstance(result, Verdict)
    assert result.criterion_results[0].unknown_reason == "evidence_class_absent"


def test_claim_id_stable_across_evidence():
    first, second = _call(), _call(evidence=_evidence(20))
    assert isinstance(first, Verdict) and isinstance(second, Verdict)
    assert first.claim_id == second.claim_id and first.verdict_id != second.verdict_id


def test_verdict_id_deterministic():
    first, second = _call(), _call()
    assert isinstance(first, Verdict) and isinstance(second, Verdict)
    assert first.verdict_id == second.verdict_id


def test_verdict_id_binds_aggregator_identity():
    first, second = _call(), _call(aggregation_evaluator_sha256="e" * 64)
    assert isinstance(first, Verdict) and isinstance(second, Verdict)
    assert first.verdict_id != second.verdict_id


def test_rule_identity_is_frozen_rc_rule():
    result = _call()
    assert isinstance(result, Verdict)
    assert result.aggregation_rule_id == FROZEN_RULE["rule_id"]
    assert result.aggregation_rule_version == FROZEN_RULE["rule_version"]


def test_refusal_id_not_fabricated_without_rc_projection():
    result = _call(gate_result=_gate(GateStatus.UNKNOWN))
    assert isinstance(result, EvaluationRefusal) and result.refusal_id is None


def test_aggregation_guard_raises_for_invalid_result():
    malformed = CriterionResult("f" * 64, "MAYBE", EvaluationTrace(C, B, {}, True), None)  # type: ignore[arg-type]
    with pytest.raises(EvaluationError):
        apply_standard_pass_fail_unknown_v0(True, [malformed])


# Independent test-only interpreter over the exact RC clause vocabulary.
_CLAUSES = {
    "spec_valid == false": lambda valid, vals: not valid,
    "true ∧ criterion_count == 0": lambda valid, vals: len(vals) == 0,
    "true ∧ any(result == FAIL)": lambda valid, vals: "FAIL" in vals,
    "true ∧ any(result == UNKNOWN)": lambda valid, vals: "UNKNOWN" in vals,
    "true ∧ all(result == PASS)": lambda valid, vals: bool(vals) and all(v == "PASS" for v in vals),
}


def _interpret(rule: dict[str, Any], valid: bool, values: list[str]) -> str:
    for clause in rule["decision_procedure"]:
        predicate = _CLAUSES.get(clause["if"])
        if predicate is None:
            raise ValueError("unrecognized declarative clause")
        if predicate(valid, values):
            return clause["return"]
    raise ValueError("declarative rule exhausted")


def _result(value: str) -> CriterionResult:
    trace = EvaluationTrace(
        C,
        B,
        {"class": "scalar", "selector": "value", "observed": 1},
        "unknown" if value == "UNKNOWN" else value == "PASS",
    )
    return CriterionResult(
        "f" * 64,
        value,  # type: ignore[arg-type]
        trace,
        "observed_inconclusive" if value == "UNKNOWN" else None,
    )


@pytest.mark.parametrize(
    "valid,values,expected",
    [
        (False, [], "REFUSE"),
        (False, ["PASS"], "REFUSE"),
        (False, ["FAIL"], "REFUSE"),
        (True, [], "REFUSE"),
        (True, ["PASS"], "VERIFIED"),
        (True, ["PASS", "PASS"], "VERIFIED"),
        (True, ["PASS", "PASS", "PASS"], "VERIFIED"),
        (True, ["FAIL"], "CONTRADICTED"),
        (True, ["PASS", "FAIL"], "CONTRADICTED"),
        (True, ["FAIL", "UNKNOWN"], "CONTRADICTED"),
        (True, ["UNKNOWN"], "INCONCLUSIVE"),
        (True, ["PASS", "UNKNOWN"], "INCONCLUSIVE"),
        (True, ["PASS", "PASS", "UNKNOWN"], "INCONCLUSIVE"),
    ],
)
def test_hardcoded_matches_declarative(valid, values, expected):
    actual = apply_standard_pass_fail_unknown_v0(valid, [_result(v) for v in values]).value
    declared = _interpret(_rule(), valid, values)
    assert actual == expected == declared
