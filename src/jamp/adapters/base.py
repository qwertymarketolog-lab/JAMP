from abc import ABC, abstractmethod
from typing import Any

from src.jamp.adapters.dto import MarketplaceType, ProductOffer


class BaseMarketplaceAdapter(ABC):
    def __init__(self, marketplace_type: MarketplaceType) -> None:
        self.marketplace_type = marketplace_type

    @abstractmethod
    async def search_products(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
    ) -> list[ProductOffer]:
        """
        Ищет товары на площадке и возвращает список нормализованных офферов.
        Каждый оффер обязательно содержит provenance_hash и raw_payload_hash.
        """
        pass
