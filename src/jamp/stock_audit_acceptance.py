from __future__ import annotations

from typing import Any


def evaluate_acceptance_rule(case: dict[str, Any], record: dict[str, Any]) -> tuple[bool, str]:
    """Evaluate a case's data-driven acceptance rule against an observed record."""
    rule = case.get("acceptance_rule")
    if not isinstance(rule, dict):
        return False, "no_acceptance_rule"

    kind = rule.get("kind")
    if kind == "stablecoin_peg":
        for rule_key, record_key in (
            ("required_status", "status"),
            ("required_evidence_status", "evidence_status"),
            ("required_e4_status", "e4_status"),
        ):
            required = rule.get(rule_key)
            if not isinstance(required, str) or not required:
                return False, f"invalid_acceptance_rule_field: {rule_key}"
            if record.get(record_key) != required:
                return False, (
                    f"{record_key} mismatch: expected {required!r}, got {record.get(record_key)!r}"
                )
        details = record.get("e4_details")
        if not isinstance(details, dict) or details.get("claim_type") != "price":
            return False, "stablecoin_peg requires CoinGecko price evidence"
        peg_value = rule.get("peg_value", 1.0)
        tolerance_pct = rule.get("tolerance_pct", 10.0)
        observed = details.get("observed_value")
        claimed = details.get("claimed_value")
        values = (peg_value, tolerance_pct, observed, claimed)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
            return False, (
                "stablecoin_peg requires numeric peg, tolerance, claimed and observed values"
            )
        if peg_value <= 0 or tolerance_pct < 0 or observed <= 0 or claimed != peg_value:
            return False, "stablecoin_peg values are invalid or claim does not match the peg"
        delta_pct = abs(observed - peg_value) / peg_value * 100.0
        if delta_pct > tolerance_pct:
            return False, f"stablecoin peg delta {delta_pct:.4f}% exceeds {tolerance_pct:.4f}%"
        return True, "stablecoin_peg matched independent CoinGecko price evidence"

    if kind == "market_cap_threshold":
        required = rule.get("required_evidence_status")
        if not isinstance(required, str) or not required:
            return False, "invalid_acceptance_rule_field: required_evidence_status"
        if record.get("evidence_status") != required:
            return False, (
                f"evidence_status mismatch: expected {required!r}, "
                f"got {record.get('evidence_status')!r}"
            )
        details = record.get("e4_details")
        threshold = rule.get("threshold_usd")
        observed = details.get("observed_value") if isinstance(details, dict) else None
        predicate = details.get("predicate_satisfied") if isinstance(details, dict) else None
        if (
            not isinstance(details, dict)
            or details.get("claim_type") != "market_cap"
            or isinstance(threshold, bool)
            or not isinstance(threshold, (int, float))
            or isinstance(observed, bool)
            or not isinstance(observed, (int, float))
            or not isinstance(predicate, bool)
        ):
            return False, "market_cap_threshold requires observed CoinGecko market-cap evidence"
        actual_predicate = observed > threshold
        if predicate is not actual_predicate:
            return False, "market_cap threshold predicate does not match observed value"
        expected_e4_status = "VERIFIED" if actual_predicate else "CONTRADICTED"
        if record.get("e4_status") != expected_e4_status:
            return False, (
                f"e4_status mismatch: expected {expected_e4_status!r}, "
                f"got {record.get('e4_status')!r}"
            )
        expected_status = "EXECUTE" if actual_predicate else "REFUSE"
        if record.get("status") != expected_status:
            return False, (
                f"status mismatch: expected {expected_status!r}, got {record.get('status')!r}"
            )
        return True, "market_cap_threshold matched the observed CoinGecko value"

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


def _evaluate_expected_behavior(expected: str, record: dict[str, Any]) -> tuple[bool, str]:
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
