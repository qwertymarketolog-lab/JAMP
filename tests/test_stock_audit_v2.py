from experiments.stock_audit.run_stock_audit_v2 import _evaluate_acceptance_rule

T23_RULE = {
    "kind": "explicit_refusal",
    "required_status": "REFUSE",
    "required_evidence_status": "VERIFIED",
    "required_response_reason": "E4_CANNOT_VERIFY_EXISTENCE",
}


def test_acceptance_rule_explicit_refusal_pass() -> None:
    case = {"id": "T23", "acceptance_rule": T23_RULE}
    record = {
        "status": "REFUSE",
        "evidence_status": "VERIFIED",
        "response_reason": "E4_CANNOT_VERIFY_EXISTENCE",
    }
    passed, reason = _evaluate_acceptance_rule(case, record)
    assert passed is True
    assert "matched all required fields" in reason


def test_acceptance_rule_wrong_status_fails() -> None:
    case = {"id": "T23", "acceptance_rule": T23_RULE}
    record = {
        "status": "EXECUTE",
        "evidence_status": "VERIFIED",
        "response_reason": "E4_CANNOT_VERIFY_EXISTENCE",
    }
    passed, _ = _evaluate_acceptance_rule(case, record)
    assert passed is False


def test_acceptance_rule_wrong_evidence_status_fails() -> None:
    case = {"id": "T23", "acceptance_rule": T23_RULE}
    record = {
        "status": "REFUSE",
        "evidence_status": "UNKNOWN",
        "response_reason": "E4_CANNOT_VERIFY_EXISTENCE",
    }
    passed, _ = _evaluate_acceptance_rule(case, record)
    assert passed is False


def test_acceptance_rule_wrong_reason_fails() -> None:
    case = {"id": "T23", "acceptance_rule": T23_RULE}
    record = {
        "status": "REFUSE",
        "evidence_status": "VERIFIED",
        "response_reason": "OTHER_REASON",
    }
    passed, _ = _evaluate_acceptance_rule(case, record)
    assert passed is False


def test_acceptance_rule_missing_returns_false() -> None:
    case = {"id": "T01"}
    record = {"status": "EXECUTE"}
    passed, reason = _evaluate_acceptance_rule(case, record)
    assert passed is False
    assert "no_acceptance_rule" in reason


def test_acceptance_rule_missing_required_field_fails_closed() -> None:
    case = {"id": "T23", "acceptance_rule": {"kind": "explicit_refusal"}}
    record = {
        "status": "REFUSE",
        "evidence_status": "VERIFIED",
        "response_reason": "E4_CANNOT_VERIFY_EXISTENCE",
    }
    passed, reason = _evaluate_acceptance_rule(case, record)
    assert passed is False
    assert "invalid_acceptance_rule_field" in reason
