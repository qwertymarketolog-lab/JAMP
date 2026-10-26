from __future__ import annotations

from experiments.stock_audit.run_stock_audit_v2 import _expected_inconclusive_response


def test_explicit_inconclusive_expectation_accepts_inconclusive_evidence() -> None:
    assert _expected_inconclusive_response("T08", "INCONCLUSIVE", "EXECUTE", "INCONCLUSIVE")


def test_explicit_inconclusive_expectation_accepts_refusal() -> None:
    assert _expected_inconclusive_response("T08", "INCONCLUSIVE", "REFUSE", "UNKNOWN")


def test_verified_case_does_not_pass_on_inconclusive_response() -> None:
    assert not _expected_inconclusive_response("T01", "VERIFIED", "EXECUTE", "INCONCLUSIVE")
    assert not _expected_inconclusive_response("T01", "VERIFIED", "REFUSE", "UNKNOWN")


def test_t23_requires_exact_critical_claim_refusal() -> None:
    assert _expected_inconclusive_response(
        "T23", "REFUSE", "REFUSE", "VERIFIED", "E4_CANNOT_VERIFY_EXISTENCE"
    )
    assert not _expected_inconclusive_response(
        "T23", "REFUSE", "REFUSE", "UNKNOWN", "E2_VERIFICATION_INCONCLUSIVE"
    )
    assert not _expected_inconclusive_response(
        "T23", "REFUSE", "REFUSE", "VERIFIED", "OTHER_REFUSAL"
    )
    assert not _expected_inconclusive_response(
        "T23", "REFUSE", "EXECUTE", "INCONCLUSIVE", "OTHER_REASON"
    )
