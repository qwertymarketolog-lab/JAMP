from dataclasses import dataclass

import pytest

from jamp.provider.ozon import ProviderDecision
from jamp.runtime.p35 import P35Executor
from jamp.runtime.router import RoutingDecision


@dataclass
class FakeRouter:
    status: str
    reason: str = "INSUFFICIENT_EVIDENCE"

    def route_task(self, task_spec):
        return RoutingDecision(
            status=self.status,
            selected_model="model-a" if self.status == "EXECUTE" else None,
            evidence_trace={"decision_reason": self.reason},
        )


@dataclass
class FakeEvidence:
    evidence_id: str = "ev:ozon:offer-1:hash"


@dataclass
class FakeProviderResult:
    decision: ProviderDecision
    reason: str | None = None
    evidence_record: FakeEvidence | None = None


class FakeProvider:
    def __init__(self, result):
        self.result = result
        self.offer_ids = []

    async def fetch_product_info(self, offer_id):
        self.offer_ids.append(offer_id)
        return self.result


@pytest.mark.asyncio
async def test_p35_execute_preserves_trace_and_calls_ozon():
    provider = FakeProvider(
        FakeProviderResult(
            decision=ProviderDecision.EXECUTE,
            evidence_record=FakeEvidence(),
        )
    )
    result = await P35Executor(
        router=FakeRouter("EXECUTE"),
        provider=provider,
    ).execute(offer_id="offer-1", trace_id="trace-exec")

    assert result.status == "EXECUTE"
    assert result.trace_id == "trace-exec"
    assert result.selected_model == "model-a"
    assert result.output == {
        "offer_id": "offer-1",
        "evidence_id": "ev:ozon:offer-1:hash",
    }
    assert provider.offer_ids == ["offer-1"]


@pytest.mark.asyncio
async def test_p35_refuse_stops_before_provider_when_router_has_no_evidence():
    provider = FakeProvider(
        FakeProviderResult(
            decision=ProviderDecision.EXECUTE,
            evidence_record=FakeEvidence(),
        )
    )
    result = await P35Executor(
        router=FakeRouter("REFUSE"),
        provider=provider,
    ).execute(offer_id="offer-1", trace_id="trace-refuse")

    assert result.status == "REFUSE"
    assert result.trace_id == "trace-refuse"
    assert result.reason == "INSUFFICIENT_EVIDENCE"
    assert provider.offer_ids == []


@pytest.mark.asyncio
async def test_p35_refuse_on_ozon_provider_failure():
    provider = FakeProvider(
        FakeProviderResult(
            decision=ProviderDecision.REFUSE,
            reason="schema_mismatch",
        )
    )
    result = await P35Executor(
        router=FakeRouter("EXECUTE"),
        provider=provider,
    ).execute(offer_id="offer-1", trace_id="trace-provider-refuse")

    assert result.status == "REFUSE"
    assert result.trace_id == "trace-provider-refuse"
    assert result.reason == "schema_mismatch"
    assert provider.offer_ids == ["offer-1"]
