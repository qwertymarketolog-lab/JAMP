from __future__ import annotations

from jamp.runtime.verdict import Claim, aggregate_verdict, critical_unverified_claims


def test_all_verified_claims_aggregate_to_verified() -> None:
    claims = [Claim("MVID exists on MOEX", "existence", "E4_MOEX", "VERIFIED")]
    assert aggregate_verdict(claims) == "VERIFIED"


def test_any_contradicted_claim_aggregates_to_contradicted() -> None:
    claims = [
        Claim("MVID exists on MOEX", "existence", "E4_MOEX", "VERIFIED"),
        Claim("price claim", "price", "E4_MOEX", "CONTRADICTED"),
    ]
    assert aggregate_verdict(claims) == "CONTRADICTED"


def test_critical_unverified_claim_aggregates_to_inconclusive() -> None:
    claims = [Claim("FakeTech IPO exists", "event", "E4_MOEX", "OUT_OF_SCOPE", critical=True)]
    assert aggregate_verdict(claims) == "INCONCLUSIVE"
    assert critical_unverified_claims(claims) == ["FakeTech IPO exists"]


def test_only_noncritical_unverified_claims_aggregate_to_partial() -> None:
    claims = [
        Claim("VKCO exists on MOEX", "existence", "E4_MOEX", "VERIFIED"),
        Claim("VKCO fell 93%", "price_movement", None, "INCONCLUSIVE"),
    ]
    assert aggregate_verdict(claims) == "PARTIAL"
    assert critical_unverified_claims(claims) == []


def test_empty_claim_list_is_partial_not_vacuously_verified() -> None:
    assert aggregate_verdict([]) == "PARTIAL"
