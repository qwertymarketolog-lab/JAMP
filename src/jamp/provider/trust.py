from __future__ import annotations

from jamp.aew.contract import EvidenceStatus

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar


T = TypeVar("T")


class SellerType(StrEnum):
    MANUFACTURER = "MANUFACTURER"
    OFFICIAL_BRAND = "OFFICIAL_BRAND"
    AUTHORIZED_RESELLER = "AUTHORIZED_RESELLER"
    RESELLER = "RESELLER"
    UNKNOWN = "UNKNOWN"


class TrustState(StrEnum):
    VERIFIED = "VERIFIED"
    INCONCLUSIVE = "INCONCLUSIVE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class EvidenceValue(Generic[T]):
    value: T | None
    status: EvidenceStatus
    source: str
    source_locator: str | None = None
    observed_at: str | None = None
    raw_hash: str | None = None


@dataclass(frozen=True)
class EvidenceRef:
    source: str
    locator: str
    status: EvidenceStatus
    identity: str | None = None
    raw_hash: str | None = None


@dataclass(frozen=True)
class SellerTrustProfile:
    seller_id: str | None
    seller_name: EvidenceValue[str] | None
    marketplace: str
    official_store: EvidenceValue[bool] | None = None
    brand: EvidenceValue[str] | None = None
    manufacturer_claim: EvidenceValue[str] | None = None
    marketplace_tenure_months: EvidenceValue[int] | None = None
    orders_count: EvidenceValue[int] | None = None
    seller_reviews_count: EvidenceValue[int] | None = None
    seller_rating: EvidenceValue[float] | None = None
    product_reviews_count: EvidenceValue[int] | None = None
    product_rating: EvidenceValue[float] | None = None
    questions_count: EvidenceValue[int] | None = None
    manufacturer_identity: EvidenceValue[str] | None = None
    manufacturer_evidence: tuple[EvidenceRef, ...] = ()
    seller_type: SellerType = SellerType.UNKNOWN
    trust_state: TrustState = TrustState.UNKNOWN


def classify_seller(profile: SellerTrustProfile) -> SellerTrustProfile:
    if not profile.seller_id:
        return _classified(profile, SellerType.UNKNOWN, TrustState.UNKNOWN)

    identities = {
        ref.identity
        for ref in profile.manufacturer_evidence
        if ref.status is EvidenceStatus.VERIFIED and ref.identity
    }
    identity_values = {
        profile.manufacturer_identity.value
    } if (
        profile.manufacturer_identity is not None
        and profile.manufacturer_identity.status is EvidenceStatus.VERIFIED
        and profile.manufacturer_identity.value
    ) else set()

    if len(identity_values) > 1:
        return _classified(profile, SellerType.UNKNOWN, TrustState.INCONCLUSIVE)

    if profile.manufacturer_identity is not None and (
        profile.manufacturer_identity.status is EvidenceStatus.INCONCLUSIVE
        or profile.manufacturer_identity.status is EvidenceStatus.CONTRADICTED
    ):
        return _classified(profile, SellerType.UNKNOWN, TrustState.INCONCLUSIVE)

    if profile.manufacturer_evidence and not identities:
        return _classified(profile, SellerType.UNKNOWN, TrustState.INCONCLUSIVE)

    if identity_values and identities:
        if identities != identity_values:
            return _classified(profile, SellerType.UNKNOWN, TrustState.INCONCLUSIVE)
        return _classified(profile, SellerType.MANUFACTURER, TrustState.VERIFIED)

    if (
        profile.official_store is not None
        and profile.official_store.status is EvidenceStatus.VERIFIED
        and profile.official_store.value is True
        and profile.brand is not None
        and profile.brand.status is EvidenceStatus.VERIFIED
        and profile.brand.value
    ):
        return _classified(profile, SellerType.OFFICIAL_BRAND, TrustState.VERIFIED)

    if (
        profile.official_store is not None
        and profile.official_store.status is EvidenceStatus.OBSERVED
    ):
        return _classified(profile, SellerType.UNKNOWN, TrustState.INCONCLUSIVE)

    return _classified(profile, SellerType.UNKNOWN, TrustState.UNKNOWN)


def eligible_for_factory_query(profile: SellerTrustProfile) -> bool:
    return (
        profile.seller_type is SellerType.MANUFACTURER
        and profile.trust_state is TrustState.VERIFIED
    )


def _classified(
    profile: SellerTrustProfile,
    seller_type: SellerType,
    trust_state: TrustState,
) -> SellerTrustProfile:
    return SellerTrustProfile(
        **{
            **profile.__dict__,
            "seller_type": seller_type,
            "trust_state": trust_state,
        }
    )


__all__ = [
    "EvidenceRef",
    "EvidenceValue",
    "SellerTrustProfile",
    "SellerType",
    "TrustState",
    "classify_seller",
    "eligible_for_factory_query",
]
