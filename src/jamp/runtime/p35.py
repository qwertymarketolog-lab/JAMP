from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from jamp.provider.ozon import OzonProviderAdapter, OzonProviderResult
from jamp.runtime.router import CapabilityRouter, RoutingDecision, TaskSpec


@dataclass(frozen=True)
class P35Result:
    status: str
    trace_id: str
    selected_model: str | None = None
    output: Any = None
    reason: str | None = None


class Router(Protocol):
    def route_task(self, task_spec: TaskSpec) -> RoutingDecision: ...


class Provider(Protocol):
    async def fetch_product_info(self, offer_id: str) -> OzonProviderResult: ...


class P35Executor:
    """Minimal fail-closed orchestration for the P35 user capability flow."""

    def __init__(
        self,
        router: Router | None = None,
        provider: Provider | None = None,
    ) -> None:
        self.router = router or CapabilityRouter()
        self.provider = provider or OzonProviderAdapter(None, None)

    async def execute(
        self,
        *,
        offer_id: str,
        trace_id: str,
        task_type: str = "marketplace:ozon",
    ) -> P35Result:
        decision = self.router.route_task(
            TaskSpec(task_type=task_type, required_confidence="VERIFIED")
        )
        if decision.status != "EXECUTE":
            reason = decision.evidence_trace.get("decision_reason", "ROUTER_REFUSE")
            return P35Result(status="REFUSE", trace_id=trace_id, reason=reason)

        if not offer_id.strip():
            return P35Result(
                status="REFUSE",
                trace_id=trace_id,
                reason="MISSING_OFFER_ID",
            )

        result = await self.provider.fetch_product_info(offer_id)
        if result.decision.value != "EXECUTE":
            return P35Result(
                status="REFUSE",
                trace_id=trace_id,
                selected_model=decision.selected_model,
                reason=result.reason or "OZON_PROVIDER_REFUSE",
            )

        return P35Result(
            status="EXECUTE",
            trace_id=trace_id,
            selected_model=decision.selected_model,
            output={
                "offer_id": offer_id,
                "evidence_id": (
                    result.evidence_record.evidence_id
                    if result.evidence_record is not None
                    else None
                ),
            },
        )


__all__ = ["P35Executor", "P35Result"]
