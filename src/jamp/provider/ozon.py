from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import httpx2 as httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from jamp.aew.contract import EvidenceRecord, EvidenceStatus


class ProviderDecision(StrEnum):
    EXECUTE = "EXECUTE"
    REFUSE = "REFUSE"


class OzonProduct(BaseModel):
    model_config = ConfigDict(extra="ignore")

    offer_id: str


class OzonProductInfoResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[OzonProduct]


@dataclass(frozen=True)
class OzonProviderResult:
    status: EvidenceStatus
    decision: ProviderDecision
    evidence_record: EvidenceRecord | None = None
    raw_hash: str | None = None
    reason: str | None = None


class OzonProviderAdapter:
    """Fail-closed Ozon Seller API provider boundary."""

    def __init__(
        self,
        client_id: str | None,
        api_key: str | None,
        *,
        base_url: str = "https://api-seller.ozon.ru",
        timeout: float = 10.0,
    ) -> None:
        self._client_id = client_id
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def fetch_product_info(self, offer_id: str) -> OzonProviderResult:
        if not self._client_id or not self._api_key:
            return self._refuse("missing_credentials")

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/v3/product/info/list",
                    headers={
                        "Client-Id": self._client_id,
                        "Api-Key": self._api_key,
                        "Content-Type": "application/json",
                    },
                    json={"offer_id": [offer_id]},
                )
        except httpx.TimeoutException:
            return self._refuse("timeout_exceeded")
        except httpx.ConnectError:
            return self._refuse("upstream_connect_error")

        if 400 <= response.status_code < 500:
            reason = (
                "upstream_auth_error"
                if response.status_code in {401, 403}
                else "upstream_client_error"
            )
            return self._refuse(reason)
        if response.status_code >= 500:
            return self._refuse("upstream_server_error")
        if response.status_code < 200 or response.status_code >= 300:
            return self._refuse("upstream_http_error")

        raw = response.content
        raw_hash = hashlib.sha256(raw).hexdigest()

        try:
            payload: Any = response.json()
            parsed = OzonProductInfoResponse.model_validate(payload)
        except (ValueError, ValidationError, TypeError):
            return self._refuse("schema_mismatch", raw_hash=raw_hash)

        if not any(product.offer_id == offer_id for product in parsed.items):
            return self._refuse("schema_mismatch", raw_hash=raw_hash)

        evidence = EvidenceRecord(
            evidence_id=f"ev:ozon:{offer_id}:{raw_hash}",
            task_id=f"ozon:get_product:{offer_id}",
            claim_id=f"claim:ozon:get_product:{offer_id}",
            source_type="ozon seller api",
            source_id=offer_id,
            raw_hash=raw_hash,
            observed_at="",
            scope="marketplace:ozon:get_product",
            status=EvidenceStatus.VERIFIED,
            metadata={
                "provider": "ozon",
                "offer_id": offer_id,
                "http_status": response.status_code,
                "endpoint": "/v3/product/info/list",
                "retrieved_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            },
        )
        return OzonProviderResult(
            status=EvidenceStatus.VERIFIED,
            decision=ProviderDecision.EXECUTE,
            evidence_record=evidence,
            raw_hash=raw_hash,
        )

    @staticmethod
    def _refuse(reason: str, *, raw_hash: str | None = None) -> OzonProviderResult:
        return OzonProviderResult(
            status=EvidenceStatus.INCONCLUSIVE,
            decision=ProviderDecision.REFUSE,
            raw_hash=raw_hash,
            reason=reason,
        )


__all__ = [
    "OzonProduct",
    "OzonProductInfoResponse",
    "OzonProviderAdapter",
    "OzonProviderResult",
    "ProviderDecision",
]
