from jamp.aew.contract import EvidenceStatus
from jamp.marketplace_runtime import (
    MarketplaceQualificationRuntime,
    OfflineMarketplaceParser,
    QualificationVerdict,
    Requirement,
)


def policy(records):
    return tuple(
        record.__class__(
            **{
                **record.__dict__,
                "status": EvidenceStatus.VERIFIED,
            }
        )
        for record in records
    )


def fixture(value=850):
    return {
        "observation_id": "fixture-001",
        "marketplace": "ozon",
        "source_locator": "fixture://ozon/001",
        "observed_at": "2026-10-02T16:00:00Z",
        "retrieved_at": "2026-10-02T16:00:01Z",
        "attributes": {"width_mm": value},
    }


def test_offline_pipeline_qualifies_verified_observation():
    observations = OfflineMarketplaceParser().parse(fixture())
    runtime = MarketplaceQualificationRuntime(policy)
    decision = runtime.run(
        observations,
        (Requirement("r1", "width_mm", "GREATER_OR_EQUAL", 800),),
        task_id="task-1",
        subject_id="product-1",
    )
    assert decision.verdict is QualificationVerdict.QUALIFIED
    assert decision.reason == "all_required_requirements_satisfied"
    assert decision.observation_ids == ("fixture-001:width_mm",)


def test_observed_evidence_cannot_qualify_without_policy_promotion():
    observations = OfflineMarketplaceParser().parse(fixture())

    runtime = MarketplaceQualificationRuntime(lambda records: tuple(records))
    decision = runtime.run(
        observations,
        (Requirement("r1", "width_mm", "EQUALS", 850),),
        task_id="task-2",
        subject_id="product-1",
    )
    assert decision.verdict is QualificationVerdict.INCONCLUSIVE
    assert decision.reason == "required_evidence_missing"


def test_missing_required_attribute_fails_closed():
    observations = OfflineMarketplaceParser().parse(fixture())
    runtime = MarketplaceQualificationRuntime(policy)
    decision = runtime.run(
        observations,
        (
            Requirement("r1", "width_mm", "EQUALS", 850),
            Requirement("r2", "height_mm", "EQUALS", 2000),
        ),
        task_id="task-3",
        subject_id="product-1",
    )
    assert decision.verdict is QualificationVerdict.INCONCLUSIVE
    assert decision.reason == "required_evidence_missing"


def test_retrieved_at_is_preserved_in_aew_metadata():
    observation = OfflineMarketplaceParser().parse(fixture())[0]
    runtime = MarketplaceQualificationRuntime(lambda records: tuple(records))
    runtime.run(
        (observation,),
        (Requirement("r1", "width_mm", "EQUALS", 850),),
        task_id="task-4",
        subject_id="product-1",
    )
    record = runtime.ledger.get("ev:fixture-001:width_mm")
    assert record.metadata["retrieved_at"] == "2026-10-02T16:00:01Z"
