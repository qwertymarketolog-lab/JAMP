from experiments.stock_audit.run_stock_audit_v2 import (
    _build_markdown_report,
    _evaluate_acceptance_rule,
    _model_response_details,
)

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



def test_model_response_details_preserves_full_output_and_provenance_path() -> None:
    response = {
        "status": "EXECUTE",
        "trace_id": "trace_example",
        "output": {"content": "x" * 240},
        "claims": [
            {"source": "E4_MOEX", "status": "VERIFIED"},
            {"source": None, "status": "INCONCLUSIVE"},
        ],
    }
    details = _model_response_details(response)
    assert details["model_response"] == "x" * 240
    assert details["model_response_reason"] is None
    assert details["provenance_url"] == "/v1/provenance/trace_example"
    assert details["e4_status"] == "VERIFIED"


def test_model_response_details_refusal_has_no_generated_response() -> None:
    details = _model_response_details(
        {
            "status": "REFUSE",
            "trace_id": "trace_refused",
            "reason": "E4_CANNOT_VERIFY_EXISTENCE",
            "output": {"content": "must not be exposed"},
        }
    )
    assert details["model_response"] is None
    assert details["model_response_reason"] == "refused_before_generation"
    assert details["provenance_url"] == "/v1/provenance/trace_refused"


def test_model_response_details_marks_conflicting_e4_claims_mixed() -> None:
    details = _model_response_details(
        {
            "status": "EXECUTE",
            "trace_id": "trace_mixed",
            "output": {"content": "answer"},
            "claims": [
                {"source": "E4_MOEX", "status": "VERIFIED"},
                {"source": "E4_MOEX", "status": "OUT_OF_SCOPE"},
            ],
        }
    )
    assert details["e4_status"] == "MIXED"


def test_markdown_report_includes_metadata_table_and_full_failure_reason() -> None:
    long_response = "model " * 45
    failure_reason = "full failure diagnostic with no truncation"
    report = {
        "result": "HOLD/FAILED",
        "cases": [
            {
                "id": "T01",
                "question": "question | one",
                "result": "FAILED",
                "status": "EXECUTE",
                "model_response": long_response,
                "model_response_reason": None,
                "provenance_url": "/v1/provenance/trace_01",
                "reason": failure_reason,
            }
        ],
    }
    markdown = _build_markdown_report(
        report, run_id="12345", sha="abc123", generated_at_utc="2026-10-26T00:00:00+00:00"
    )
    assert "Run ID: 12345" in markdown
    assert "SHA: abc123" in markdown
    assert "Date (UTC): 2026-10-26T00:00:00+00:00" in markdown
    assert "| ID | Вопрос | Статус | Ответ модели | Ссылка на provenance |" in markdown
    assert "question \\| one" in markdown
    assert "[provenance](/v1/provenance/trace_01)" in markdown
    assert failure_reason in markdown
    table_row = next(line for line in markdown.splitlines() if line.startswith("| T01 |"))
    assert len(table_row.split("|")[4]) <= 202
