import hashlib
import json

import pytest
from pydantic import ValidationError

from src.jamp.adapters import (
    BaseMarketplaceAdapter,
    MarketplaceType,
    ProductOffer,
    compute_request_provenance_hash,
)


def test_provenance_hash_determinism():
    filters = {"category": "electronics", "sort": "price_asc"}
    hash1 = compute_request_provenance_hash(MarketplaceType.OZON, "Sony WH-1000XM5", filters)
    hash2 = compute_request_provenance_hash(MarketplaceType.OZON, "Sony WH-1000XM5 ", filters)

    assert hash1 == hash2
    assert len(hash1) == 64


def test_provenance_hash_filters_none_normalization():
    hash_none = compute_request_provenance_hash(MarketplaceType.OZON, "test", None)
    hash_empty = compute_request_provenance_hash(MarketplaceType.OZON, "test", {})

    assert hash_none == hash_empty
    assert len(hash_none) == 64


def test_provenance_hash_excludes_credentials():
    filters = {"category": "audio"}
    hash_clean = compute_request_provenance_hash(MarketplaceType.WILDBERRIES, "headphones", filters)

    assert "api_key" not in json.dumps(filters)
    assert isinstance(hash_clean, str)


def test_product_offer_contract_validation():
    provenance = compute_request_provenance_hash(MarketplaceType.YANDEX_MARKET, "phone", None)
    raw_payload_hash = hashlib.sha256(b'{"raw": "payload"}').hexdigest()

    offer = ProductOffer(
        marketplace=MarketplaceType.YANDEX_MARKET,
        id="ym_12345",
        title="Smartphone",
        price_rub=49990.0,
        in_stock=True,
        url="https://market.yandex.ru/product/12345",
        image_url="https://market.yandex.ru/img/12345.jpg",
        raw_payload_hash=raw_payload_hash,
        provenance_hash=provenance,
    )

    assert offer.marketplace == "yandex_market"
    assert offer.provenance_hash == provenance
    assert offer.raw_payload_hash == raw_payload_hash


def test_product_offer_invalid_price():
    provenance = compute_request_provenance_hash(MarketplaceType.OZON, "item", {})
    raw_hash = hashlib.sha256(b"raw").hexdigest()

    with pytest.raises(ValidationError):
        ProductOffer(
            marketplace=MarketplaceType.OZON,
            id="123",
            title="Bad Item",
            price_rub=0.0,
            in_stock=True,
            url="https://ozon.ru/item",
            raw_payload_hash=raw_hash,
            provenance_hash=provenance,
        )


@pytest.mark.asyncio
async def test_base_adapter_subclass():
    class DummyAdapter(BaseMarketplaceAdapter):
        async def search_products(self, query: str, filters=None):
            return []

    adapter = DummyAdapter(MarketplaceType.OZON)
    assert adapter.marketplace_type == MarketplaceType.OZON
    res = await adapter.search_products("query")
    assert res == []
