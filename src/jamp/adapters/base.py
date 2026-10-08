from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from src.jamp.adapters.dto import MarketplaceType, ProductOffer


class BaseMarketplaceAdapter(ABC):
    def __init__(self, marketplace_type: MarketplaceType) -> None:
        self.marketplace_type = marketplace_type

    @abstractmethod
    async def search_products(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[ProductOffer]:
        """
        Ищет товары на площадке и возвращает список нормализованных офферов.
        Каждый оффер обязательно содержит provenance_hash и raw_payload_hash.
        """
        pass
