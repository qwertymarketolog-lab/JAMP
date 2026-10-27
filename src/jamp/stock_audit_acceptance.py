from __future__ import annotations

from typing import Any


def evaluate_acceptance_rule(case: dict[str, Any], record: dict[str, Any]) -> tuple[bool, str]:
    """Evaluate a case's data-driven acceptance rule against an observed record."""
    rule = case.get("acceptance_rule")
    if not isinstance(rule, dict):
        return False, "no_acceptance_rule"

    kind = rule.get("kind")
    if kind != "explicit_refusal":
        return False, f"unsupported_acceptance_rule_kind: {kind!r}"

    required_fields = (
        ("required_status", "status"),
        ("required_evidence_status", "evidence_status"),
        ("required_response_reason", "response_reason"),
    )
    validated_fields: list[tuple[str, str]] = []
    for rule_key, record_key in required_fields:
        required = rule.get(rule_key)
        if not isinstance(required, str) or not required:
            return False, f"invalid_acceptance_rule_field: {rule_key}"
        validated_fields.append((record_key, required))

    for record_key, required in validated_fields:
        observed = record.get(record_key)
        if observed != required:
            return False, (f"{record_key} mismatch: expected {required!r}, got {observed!r}")

    return True, "acceptance_rule explicit_refusal matched all required fields"

def _evaluate_expected_behavior(
    expected: str, record: dict[str, Any]
) -> tuple[bool, str]:
    """Evaluate expected_behavior against the observed record, without I/O."""
    status = record.get("status")
    evidence_status = record.get("evidence_status")
    aggregate_status = record.get("aggregate_status")

    if expected == "VERIFIED":
        if record.get("http_status") != 200:
            return False, f"expected HTTP 200, got {record.get('http_status')!r}"
        if status != "EXECUTE":
            return False, f"expected EXECUTE, got {status!r}"
        if evidence_status != "VERIFIED":
            return False, f"expected evidence_status VERIFIED, got {evidence_status!r}"
        if record.get("verdict_valid") is not True:
            return False, f"expected verdict_valid True, got {record.get('verdict_valid')!r}"
        return True, (
            "HTTP execution, evidence_status, signed-verdict validation and provenance verified; "
            "factual correctness is not independently established by this harness"
        )

    if expected == "PARTIAL":
        if status == "EXECUTE" and aggregate_status == "PARTIAL":
            return True, "EXECUTE with explicitly expected PARTIAL claim-level verdict"
        return False, (
            "expected EXECUTE + aggregate_status PARTIAL, got "
            f"status={status!r}, aggregate_status={aggregate_status!r}"
        )

    if expected in {"INCONCLUSIVE", "INCONCLUSIVE/REFUSE"}:
        if status in {"INCONCLUSIVE", "REFUSE"}:
            return True, "explicit refusal/inconclusive response matches case expectation"
        return False, (
            "expected refusal/inconclusive, got "
            f"status={status!r}, evidence_status={evidence_status!r}"
        )

    if expected == "REFUSE":
        if status == "REFUSE":
            return True, "explicit refusal matches case expectation"
        return False, f"expected REFUSE, got {status!r}"

    return False, f"unsupported_expected_behavior: {expected!r}"


def evaluate_acceptance(case: dict[str, Any], record: dict[str, Any]) -> tuple[bool, str]:
    """Apply an explicit acceptance rule first, otherwise evaluate expected_behavior."""
    if "acceptance_rule" in case:
        return evaluate_acceptance_rule(case, record)
    expected = case.get("expected_behavior")
    if not isinstance(expected, str):
        return False, "missing_or_invalid_expected_behavior"
    return _evaluate_expected_behavior(expected, record)

