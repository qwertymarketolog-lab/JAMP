"""Fail-closed Policy Gate for Phase A."""

from __future__ import annotations

from enum import StrEnum


class Decision(StrEnum):
    ALLOW = "ALLOW"
    REJECT = "REJECT"
    INCONCLUSIVE = "INCONCLUSIVE"


def evaluate(*, path_allowed: bool, required_evidence_present: bool) -> Decision:
    if not path_allowed:
        return Decision.REJECT
    if not required_evidence_present:
        return Decision.INCONCLUSIVE
    return Decision.ALLOW
