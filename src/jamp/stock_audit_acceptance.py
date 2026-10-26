from __future__ import annotations

from typing import Any


def evaluate_acceptance_rule(
    case: dict[str, Any], record: dict[str, Any]
) -> tuple[bool, str]:
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
