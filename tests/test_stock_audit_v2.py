from __future__ import annotations

from experiments.stock_audit.run_stock_audit_v2 import _expected_inconclusive_response


def test_t07_inconclusive_is_pass_for_explicit_inconclusive_expectation() -> None:
    assert _expected_inconclusive_response("T07", "INCONCLUSIVE", "EXECUTE", "INCONCLUSIVE")


def test_t07_refusal_is_pass_for_explicit_inconclusive_expectation() -> None:
    assert _expected_inconclusive_response("T07", "INCONCLUSIVE", "REFUSE", "UNKNOWN")


def test_verified_case_does_not_pass_on_inconclusive_response() -> None:
    assert not _expected_inconclusive_response("T01", "VERIFIED", "EXECUTE", "INCONCLUSIVE")
    assert not _expected_inconclusive_response("T01", "VERIFIED", "REFUSE", "UNKNOWN")


def test_t23_accepts_explicit_refusal_or_inconclusive_evidence() -> None:
    assert _expected_inconclusive_response("T23", "INCONCLUSIVE/REFUSE", "REFUSE", "UNKNOWN")
    assert _expected_inconclusive_response("T23", "INCONCLUSIVE/REFUSE", "EXECUTE", "INCONCLUSIVE")
    assert not _expected_inconclusive_response("T23", "INCONCLUSIVE/REFUSE", "EXECUTE", "VERIFIED")
