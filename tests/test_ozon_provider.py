from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jamp.aew.contract import EvidenceStatus
from jamp.provider.ozon import OzonProviderAdapter, ProviderDecision


def response(status_code: int, payload: object, raw: bytes | None = None):
    result = MagicMock()
    result.status_code = status_code
    result.content = raw if raw is not None else b'{"items":[{"offer_id":"offer-1"}]}'
    result.json.return_value = payload
    return result


@pytest.mark.asyncio
async def test_ozon_200_valid_schema():
    http = AsyncMock()
    http.post.return_value = response(200, {"items": [{"offer_id": "offer-1"}]})
    with patch("jamp.provider.ozon.httpx.AsyncClient") as factory:
        factory.return_value.__aenter__.return_value = http
        result = await OzonProviderAdapter("client", "key").fetch_product_info("offer-1")

    assert result.status is EvidenceStatus.VERIFIED
    assert result.decision is ProviderDecision.EXECUTE
    assert result.evidence_record is not None
    assert result.raw_hash
    http.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_ozon_200_invalid_schema():
    http = AsyncMock()
    http.post.return_value = response(200, {"items": [{"product_id": "123"}]})
    with patch("jamp.provider.ozon.httpx.AsyncClient") as factory:
        factory.return_value.__aenter__.return_value = http
        result = await OzonProviderAdapter("client", "key").fetch_product_info("offer-1")

    assert result.status is EvidenceStatus.INCONCLUSIVE
    assert result.decision is ProviderDecision.REFUSE
    assert result.reason == "schema_mismatch"


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403])
async def test_ozon_401_unauthorized(status_code):
    http = AsyncMock()
    http.post.return_value = response(status_code, {"error": "unauthorized"})
    with patch("jamp.provider.ozon.httpx.AsyncClient") as factory:
        factory.return_value.__aenter__.return_value = http
        result = await OzonProviderAdapter("client", "key").fetch_product_info("offer-1")

    assert result.status is EvidenceStatus.INCONCLUSIVE
    assert result.decision is ProviderDecision.REFUSE
    assert result.reason == "upstream_auth_error"


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [500, 502, 503])
async def test_ozon_5xx_server_error(status_code):
    http = AsyncMock()
    http.post.return_value = response(status_code, {"error": "server"})
    with patch("jamp.provider.ozon.httpx.AsyncClient") as factory:
        factory.return_value.__aenter__.return_value = http
        result = await OzonProviderAdapter("client", "key").fetch_product_info("offer-1")

    assert result.status is EvidenceStatus.INCONCLUSIVE
    assert result.decision is ProviderDecision.REFUSE
    assert result.reason == "upstream_server_error"


@pytest.mark.asyncio
async def test_ozon_timeout():
    http = AsyncMock()
    http.post.side_effect = __import__("httpx2").TimeoutException("timeout")
    with patch("jamp.provider.ozon.httpx.AsyncClient") as factory:
        factory.return_value.__aenter__.return_value = http
        result = await OzonProviderAdapter("client", "key").fetch_product_info("offer-1")

    assert result.status is EvidenceStatus.INCONCLUSIVE
    assert result.decision is ProviderDecision.REFUSE
    assert result.reason == "timeout_exceeded"


@pytest.mark.asyncio
async def test_ozon_missing_credentials():
    with patch("jamp.provider.ozon.httpx.AsyncClient") as factory:
        result = await OzonProviderAdapter(None, "key").fetch_product_info("offer-1")

    assert result.status is EvidenceStatus.INCONCLUSIVE
    assert result.decision is ProviderDecision.REFUSE
    assert result.reason == "missing_credentials"
    factory.assert_not_called()
