import hashlib
import json
from enum import StrEnum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, HttpUrl


class MarketplaceType(StrEnum):
    OZON = "ozon"
    WILDBERRIES = "wildberries"
    YANDEX_MARKET = "yandex_market"


class ProductOffer(BaseModel):
    marketplace: MarketplaceType
    id: str = Field(..., description="ID товара на площадке")
    title: str = Field(..., description="Наименование товара")
    price_rub: float = Field(..., gt=0, description="Цена в рублях")
    in_stock: bool = Field(..., description="Статус наличия")
    url: HttpUrl = Field(..., description="Прямая ссылка на товар")
    image_url: Optional[HttpUrl] = Field(None, description="Ссылка на изображение товара")
    raw_payload_hash: str = Field(..., description="SHA-256 хэш сырого ответа API маркетплейса")
    provenance_hash: str = Field(..., description="Детерминированный SHA-256 хэш контекста запроса")


def compute_request_provenance_hash(
    marketplace: MarketplaceType,
    query: str,
    filters: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Вычисляет детерминированный SHA-256 хэш контекста запроса.
    Гарантирует обработку filters=None и нормализацию структуры.
    Секреты/credentials НЕ включаются в хэш.
    """
    safe_filters = filters or {}
    normalized_payload = {
        "marketplace": str(marketplace),
        "query": query.strip().lower(),
        "filters": {
            k: sorted(v) if isinstance(v, list) else v
            for k, v in sorted(safe_filters.items())
        },
    }
    dumped = json.dumps(normalized_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()
