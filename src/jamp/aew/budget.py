"""AEW model budget and escalation contract.

This module is policy-only: it does not call providers or infer pricing.
Unknown token/cost estimates fail closed, and escalation is never implicit.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetUsage:
    """Cumulative usage already committed to an AEW task."""

    tokens: int = 0
    calls: int = 0
    spend_usd: float = 0.0


@dataclass(frozen=True)
class BudgetDecision:
    """Fail-closed authorization result for one prospective model call."""

    allowed: bool
    escalation: bool
    reason: str


@dataclass(frozen=True)
class ModelBudgetPolicy:
    """Hard limits for one AEW worker/task budget.

    ``token_budget``, ``max_calls`` and ``spend_cap_usd`` are hard caps.
    Provider pricing is supplied by the caller; this contract never guesses it.
    Escalation is denied unless explicitly enabled and still within all caps.
    """

    token_budget: int
    max_calls: int
    spend_cap_usd: float
    escalation_enabled: bool = False

    def __post_init__(self) -> None:
        if self.token_budget <= 0:
            raise ValueError("token_budget must be > 0")
        if self.max_calls <= 0:
            raise ValueError("max_calls must be > 0")
        if self.spend_cap_usd < 0:
            raise ValueError("spend_cap_usd must be >= 0")

    def authorize(
        self,
        usage: BudgetUsage,
        *,
        estimated_tokens: int | None,
        estimated_cost_usd: float | None,
        escalation: bool = False,
    ) -> BudgetDecision:
        """Authorize a prospective call without mutating usage.

        Missing estimates are UNKNOWN and therefore denied. A call that would
        cross any hard cap is denied. Escalation is denied unless explicitly
        enabled; there is no automatic fallback to an unbudgeted model.
        """
        if usage.tokens < 0 or usage.calls < 0 or usage.spend_usd < 0:
            return BudgetDecision(False, escalation, "INVALID_USAGE")
        if estimated_tokens is None or estimated_cost_usd is None:
            return BudgetDecision(False, escalation, "MISSING_COST_ESTIMATE")
        if estimated_tokens < 0 or estimated_cost_usd < 0:
            return BudgetDecision(False, escalation, "INVALID_COST_ESTIMATE")
        if escalation and not self.escalation_enabled:
            return BudgetDecision(False, True, "ESCALATION_DISABLED")
        if usage.calls + 1 > self.max_calls:
            return BudgetDecision(False, escalation, "MAX_CALLS_EXCEEDED")
        if usage.tokens + estimated_tokens > self.token_budget:
            return BudgetDecision(False, escalation, "TOKEN_BUDGET_EXCEEDED")
        if usage.spend_usd + estimated_cost_usd > self.spend_cap_usd:
            return BudgetDecision(False, escalation, "SPEND_CAP_EXCEEDED")
        return BudgetDecision(True, escalation, "AUTHORIZED")
