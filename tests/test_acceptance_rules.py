from __future__ import annotations

from typing import Any

from jamp.stock_audit_acceptance import evaluate_acceptance

VERIFIED_RECORD: dict[str, Any] = {
    "http_status": 200,
    "status": "EXECUTE",
    "evidence_status": "VERIFIED",
    "aggregate_status": "VERIFIED",
    "verdict_valid": True,
}


def test_verified_accepts_complete_evidence_and_valid_verdict() -> None:
    passed, reason = evaluate_acceptance({"expected_behavior": "VERIFIED"}, VERIFIED_RECORD)
    assert passed is True
    assert "signed-verdict validation" in reason


def test_verified_rejects_non_200_http() -> None:
    passed, reason = evaluate_acceptance(
        {"expected_behavior": "VERIFIED"}, {**VERIFIED_RECORD, "http_status": 502}
    )
    assert passed is False
    assert "HTTP 200" in reason


def test_verified_rejects_non_execute_status() -> None:
    passed, reason = evaluate_acceptance(
        {"expected_behavior": "VERIFIED"}, {**VERIFIED_RECORD, "status": "REFUSE"}
    )
    assert passed is False
    assert "EXECUTE" in reason


def test_verified_rejects_non_verified_evidence() -> None:
    passed, reason = evaluate_acceptance(
        {"expected_behavior": "VERIFIED"}, {**VERIFIED_RECORD, "evidence_status": "UNKNOWN"}
    )
    assert passed is False
    assert "evidence_status VERIFIED" in reason


def test_verified_rejects_invalid_signature_verdict() -> None:
    passed, reason = evaluate_acceptance(
        {"expected_behavior": "VERIFIED"}, {**VERIFIED_RECORD, "verdict_valid": False}
    )
    assert passed is False
    assert "verdict_valid True" in reason


def test_partial_accepts_execute_with_partial_aggregate_and_any_evidence() -> None:
    passed, reason = evaluate_acceptance(
        {"expected_behavior": "PARTIAL"},
        {"status": "EXECUTE", "evidence_status": "UNKNOWN", "aggregate_status": "PARTIAL"},
    )
    assert passed is True
    assert "PARTIAL" in reason


def test_partial_rejects_refusal_status() -> None:
    passed, reason = evaluate_acceptance(
        {"expected_behavior": "PARTIAL"}, {"status": "REFUSE", "aggregate_status": "PARTIAL"}
    )
    assert passed is False
    assert "EXECUTE" in reason


def test_partial_rejects_verified_aggregate() -> None:
    passed, reason = evaluate_acceptance(
        {"expected_behavior": "PARTIAL"},
        {"status": "EXECUTE", "aggregate_status": "VERIFIED"},
    )
    assert passed is False
    assert "aggregate_status PARTIAL" in reason


def test_partial_rejects_missing_aggregate() -> None:
    passed, reason = evaluate_acceptance({"expected_behavior": "PARTIAL"}, {"status": "EXECUTE"})
    assert passed is False
    assert "aggregate_status PARTIAL" in reason


def test_partial_does_not_require_a_valid_verdict() -> None:
    passed, _ = evaluate_acceptance(
        {"expected_behavior": "PARTIAL"},
        {"status": "EXECUTE", "aggregate_status": "PARTIAL", "verdict_valid": None},
    )
    assert passed is True


def test_inconclusive_accepts_inconclusive_status() -> None:
    passed, _ = evaluate_acceptance(
        {"expected_behavior": "INCONCLUSIVE"}, {"status": "INCONCLUSIVE"}
    )
    assert passed is True


def test_inconclusive_accepts_refuse_status() -> None:
    passed, _ = evaluate_acceptance({"expected_behavior": "INCONCLUSIVE"}, {"status": "REFUSE"})
    assert passed is True


def test_inconclusive_refuse_alias_accepts_refuse_status() -> None:
    passed, _ = evaluate_acceptance(
        {"expected_behavior": "INCONCLUSIVE/REFUSE"}, {"status": "REFUSE"}
    )
    assert passed is True


def test_inconclusive_rejects_execute_even_with_inconclusive_evidence() -> None:
    passed, reason = evaluate_acceptance(
        {"expected_behavior": "INCONCLUSIVE"},
        {"status": "EXECUTE", "evidence_status": "INCONCLUSIVE"},
    )
    assert passed is False
    assert "refusal/inconclusive" in reason


def test_inconclusive_rejects_execute_with_partial_aggregate() -> None:
    passed, _ = evaluate_acceptance(
        {"expected_behavior": "INCONCLUSIVE"},
        {"status": "EXECUTE", "aggregate_status": "PARTIAL"},
    )
    assert passed is False


def test_refuse_accepts_refuse_status() -> None:
    passed, _ = evaluate_acceptance({"expected_behavior": "REFUSE"}, {"status": "REFUSE"})
    assert passed is True


def test_refuse_ignores_evidence_status() -> None:
    passed, _ = evaluate_acceptance(
        {"expected_behavior": "REFUSE"}, {"status": "REFUSE", "evidence_status": "UNKNOWN"}
    )
    assert passed is True


def test_refuse_ignores_aggregate_and_verdict_fields() -> None:
    passed, _ = evaluate_acceptance(
        {"expected_behavior": "REFUSE"},
        {"status": "REFUSE", "aggregate_status": "PARTIAL", "verdict_valid": False},
    )
    assert passed is True


def test_refuse_rejects_inconclusive_status() -> None:
    passed, reason = evaluate_acceptance(
        {"expected_behavior": "REFUSE"}, {"status": "INCONCLUSIVE"}
    )
    assert passed is False
    assert "expected REFUSE" in reason


def test_refuse_rejects_execute_status() -> None:
    passed, _ = evaluate_acceptance({"expected_behavior": "REFUSE"}, {"status": "EXECUTE"})
    assert passed is False


def test_explicit_acceptance_rule_has_priority_over_expected_behavior() -> None:
    case = {
        "expected_behavior": "VERIFIED",
        "acceptance_rule": {
            "kind": "explicit_refusal",
            "required_status": "REFUSE",
            "required_evidence_status": "VERIFIED",
            "required_response_reason": "E4_CANNOT_VERIFY_EXISTENCE",
        },
    }
    record = {
        "status": "REFUSE",
        "evidence_status": "VERIFIED",
        "response_reason": "E4_CANNOT_VERIFY_EXISTENCE",
    }
    passed, reason = evaluate_acceptance(case, record)
    assert passed is True
    assert "acceptance_rule" in reason
