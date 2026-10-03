import json
from pathlib import Path

from jamp.aew.contract import EvidenceStatus
from jamp.marketplace_runtime import (
    MarketplaceQualificationRuntime,
    OfflineMarketplaceParser,
    ParserStatus,
    QualificationVerdict,
    RawObservation,
    Requirement,
)


FIXTURE = Path(__file__).parents[1] / "fixtures" / "marketplace_product_payload.json"


def promote(records):
    return tuple(
        record.__class__(
            **{
                **record.__dict__,
                "status": EvidenceStatus.VERIFIED,
            }
        )
        for record in records
    )


def ai_double(provider: str, value: int) -> RawObservation:
    return RawObservation(
        observation_id=f"ai:{provider}:product-001:width_mm",
        marketplace="offline-ai",
        source_locator=f"fixture://{provider}/product-001",
        observed_at="2026-10-03T00:00:02Z",
        retrieved_at="2026-10-03T00:00:02Z",
        raw_value={"provider": provider, "width_mm": value},
        canonical_attribute="width_mm",
        normalized_value=value,
        status=ParserStatus.OBSERVED,
    )


def test_offline_vertical_slice_marketplace_three_ai_to_decision_audit():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    parser_observations = OfflineMarketplaceParser().parse(fixture)
    assert parser_observations

    ai_observations = tuple(
        ai_double(provider, fixture["attributes"]["width_mm"])
        for provider in ("gemini", "claude", "gpt")
    )

    observations = parser_observations + ai_observations
    runtime = MarketplaceQualificationRuntime(promote)
    decision = runtime.run(
        observations,
        (Requirement("width-min", "width_mm", "GREATER_OR_EQUAL", 800),),
        task_id="offline-vertical-slice",
        subject_id="ozon:product-001",
    )

    assert decision.verdict is QualificationVerdict.QUALIFIED
    assert decision.reason == "all_required_requirements_satisfied"

    audit = runtime.audit_records[-1]
    assert audit.decision is decision
    assert len(audit.requirement_evaluations) == 1
    evaluation = audit.requirement_evaluations[0]
    assert evaluation.requirement_id == "width-min"
    assert evaluation.evaluation_status == "SATISFIED"
    assert evaluation.actual_value == 850
    assert len(evaluation.evidence_ids) == 4
    assert set(audit.observation_ids) == {
        "marketplace-product-001:width_mm",
        "marketplace-product-001:title",
        "ai:gemini:product-001:width_mm",
        "ai:claude:product-001:width_mm",
        "ai:gpt:product-001:width_mm",
    }
    assert audit.decision_digest == decision.decision_digest
