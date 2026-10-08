from jamp.aew.contract import EvidenceStatus
from jamp.provider.trust import (
    EvidenceRef,
    EvidenceValue,
    SellerTrustProfile,
    SellerType,
    TrustState,
    classify_seller,
    eligible_for_factory_query,
)


def ev(value, status=EvidenceStatus.OBSERVED):
    return EvidenceValue(value=value, status=status, source="ozon")


def manufacturer_ref(name="official-manufacturer"):
    return EvidenceRef(
        source="official_manufacturer",
        locator=name,
        status=EvidenceStatus.VERIFIED,
        identity="Реноме" if name == "official-renome" else "Other Manufacturer",
    )


def profile(**kwargs):
    return SellerTrustProfile(
        seller_id="seller-1",
        seller_name=ev("Реноме"),
        marketplace="ozon",
        **kwargs,
    )


def test_st_001_complete_verified_manufacturer():
    result = classify_seller(
        profile(
            official_store=ev(True, EvidenceStatus.VERIFIED),
            brand=ev("Реноме", EvidenceStatus.VERIFIED),
            manufacturer_identity=ev("Реноме", EvidenceStatus.VERIFIED),
            manufacturer_evidence=(manufacturer_ref(),),
        )
    )

    assert result.seller_type is SellerType.MANUFACTURER
    assert result.trust_state is TrustState.VERIFIED


def test_st_002_official_store_without_manufacturer():
    result = classify_seller(
        profile(
            official_store=ev(True, EvidenceStatus.VERIFIED),
            brand=ev("Реноме", EvidenceStatus.VERIFIED),
        )
    )

    assert result.seller_type is SellerType.OFFICIAL_BRAND
    assert result.trust_state is TrustState.VERIFIED


def test_st_003_high_orders_do_not_prove_manufacturer():
    result = classify_seller(
        profile(
            orders_count=ev(428_000),
            seller_rating=ev(4.9),
            marketplace_tenure_months=ev(48),
        )
    )

    assert result.seller_type is SellerType.UNKNOWN
    assert result.trust_state is TrustState.UNKNOWN


def test_st_004_high_rating_do_not_prove_manufacturer():
    result = classify_seller(
        profile(
            product_rating=ev(4.9),
            product_reviews_count=ev(18_301),
            seller_reviews_count=ev(109_000),
        )
    )

    assert result.seller_type is SellerType.UNKNOWN
    assert result.trust_state is TrustState.UNKNOWN


def test_st_005_manufacturer_claim_only():
    result = classify_seller(
        profile(
            manufacturer_claim=ev("Реноме", EvidenceStatus.OBSERVED),
        )
    )

    assert result.seller_type is SellerType.UNKNOWN
    assert result.trust_state is TrustState.UNKNOWN


def test_st_006_missing_manufacturer_evidence():
    result = classify_seller(
        profile(
            manufacturer_identity=ev("Реноме", EvidenceStatus.OBSERVED),
        )
    )

    assert result.seller_type is SellerType.UNKNOWN
    assert result.trust_state is TrustState.UNKNOWN


def test_st_007_conflicting_manufacturer_sources():
    result = classify_seller(
        profile(
            manufacturer_identity=ev("Реноме", EvidenceStatus.VERIFIED),
            manufacturer_evidence=(
                manufacturer_ref("official-renome"),
                manufacturer_ref("conflicting-source"),
            ),
        )
    )

    assert result.seller_type is SellerType.MANUFACTURER
    assert result.trust_state is TrustState.VERIFIED


def test_st_008_unknown_seller_identity():
    result = classify_seller(
        SellerTrustProfile(
            seller_id=None,
            seller_name=None,
            marketplace="ozon",
            manufacturer_identity=ev("Реноме", EvidenceStatus.VERIFIED),
            manufacturer_evidence=(manufacturer_ref(),),
        )
    )

    assert result.seller_type is SellerType.UNKNOWN
    assert result.trust_state is TrustState.UNKNOWN


def test_st_009_reseller_filtered_for_factory_query():
    result = classify_seller(
        profile(
            official_store=ev(False, EvidenceStatus.VERIFIED),
        )
    )

    assert not eligible_for_factory_query(result)


def test_st_010_deterministic_trust_state():
    candidate = profile(
        official_store=ev(True, EvidenceStatus.VERIFIED),
        brand=ev("Реноме", EvidenceStatus.VERIFIED),
    )

    first = classify_seller(candidate)
    second = classify_seller(candidate)

    assert first == second
    assert first.seller_type is SellerType.OFFICIAL_BRAND
    assert first.trust_state is TrustState.VERIFIED
