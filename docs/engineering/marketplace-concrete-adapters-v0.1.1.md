# Concrete Marketplace Adapters v0.1.1 — Design Contract

## Purpose

This design-only contract defines concrete Ozon, Wildberries, and Yandex Market
adapter boundaries on top of `MarketplaceSourceAdapter v0.1.1`.

It specifies source-specific extraction and provenance mapping only. It does
not authorize network requests, runtime integration, evidence promotion, or
CI workflow changes.

## Contract boundary

```text
RawObservation
    |
    v
BaseMarketplaceAdapter.extract_claims()
    |
    +--> _parse_payload_to_claims()
    |
    v
Claims [OBSERVED | UNKNOWN]
    |
    v
EvidencePolicy.evaluate()
    |
    v
Claims [VERIFIED | UNKNOWN]
```

### Strict status isolation

Concrete adapters MUST NOT emit `ClaimStatus.VERIFIED`.

- present source values -> `OBSERVED`
- absent/unavailable source values -> `UNKNOWN`
- `EvidencePolicy` remains the sole `OBSERVED -> VERIFIED` boundary
- adapter parsing MUST NOT infer missing values or apply decision confidence

A defensive base implementation MAY normalize an invalid parser status back
to `OBSERVED` when a value is present, otherwise `UNKNOWN`. Such defensive
normalization is a contract guard, not evidence verification.

## Declarative interface

```python
from abc import abstractmethod
from typing import Any, Dict, List

from jamp.marketplace.base import (
    Claim,
    ClaimStatus,
    MarketplaceSourceAdapter,
    RawObservation,
)


class BaseMarketplaceAdapter(MarketplaceSourceAdapter):
    """Source adapter boundary with strict OBSERVED/UNKNOWN isolation."""

    def extract_claims(self, observation: RawObservation) -> List[Claim]:
        extracted = self._parse_payload_to_claims(observation.raw_payload)
        normalized: List[Claim] = []

        for claim in extracted:
            if claim.status not in (
                ClaimStatus.OBSERVED,
                ClaimStatus.UNKNOWN,
            ):
                claim = Claim(
                    attribute_name=claim.attribute_name,
                    value=claim.value,
                    status=(
                        ClaimStatus.OBSERVED
                        if claim.value is not None
                        else ClaimStatus.UNKNOWN
                    ),
                    raw_source_value=claim.raw_source_value,
                    metadata=claim.metadata,
                )
            normalized.append(claim)

        return normalized

    @abstractmethod
    def _parse_payload_to_claims(
        self, payload: Dict[str, Any]
    ) -> List[Claim]:
        pass


class OzonSourceAdapter(BaseMarketplaceAdapter):
    """Ozon Seller API v2/v3 — design contract only."""

    @property
    def source_name(self) -> str:
        return "ozon"

    def fetch_raw_observation(self, product_id: str) -> RawObservation:
        raise NotImplementedError(
            "Design contract only: runtime API calls disabled"
        )

    def _parse_payload_to_claims(
        self, payload: Dict[str, Any]
    ) -> List[Claim]:
        attributes = payload.get("attributes", [])
        attr_map = {
            "Материал": "material",
            "Ширина": "width_mm",
            "Высота": "height_mm",
            "Количество дверей": "doors_count",
        }
        claims: List[Claim] = []

        for attr in attributes:
            raw_name = attr.get("name")
            raw_values = attr.get("values", [])
            raw_val = raw_values[0] if raw_values else None

            if raw_name in attr_map:
                claims.append(
                    Claim(
                        attribute_name=attr_map[raw_name],
                        value=raw_val,
                        status=(
                            ClaimStatus.OBSERVED
                            if raw_val is not None
                            else ClaimStatus.UNKNOWN
                        ),
                        raw_source_value=raw_val,
                        metadata={
                            "ozon_attribute_id": attr.get("id"),
                            "raw_name": raw_name,
                        },
                    )
                )

        return claims


class WildberriesSourceAdapter(BaseMarketplaceAdapter):
    """Wildberries Content API v2 — design contract only."""

    @property
    def source_name(self) -> str:
        return "wildberries"

    def fetch_raw_observation(self, product_id: str) -> RawObservation:
        raise NotImplementedError(
            "Design contract only: runtime API calls disabled"
        )

    def _parse_payload_to_claims(
        self, payload: Dict[str, Any]
    ) -> List[Claim]:
        options = payload.get("options", [])
        attr_map = {
            "Материал корпуса": "material",
            "Ширина предмета": "width_mm",
            "Высота предмета": "height_mm",
            "Количество створок": "doors_count",
        }
        claims: List[Claim] = []

        for opt in options:
            raw_name = opt.get("name")
            raw_val = opt.get("value")

            if raw_name in attr_map:
                claims.append(
                    Claim(
                        attribute_name=attr_map[raw_name],
                        value=raw_val,
                        status=(
                            ClaimStatus.OBSERVED
                            if raw_val is not None
                            else ClaimStatus.UNKNOWN
                        ),
                        raw_source_value=raw_val,
                        metadata={"wb_option_name": raw_name},
                    )
                )

        return claims


class YandexMarketSourceAdapter(BaseMarketplaceAdapter):
    """Yandex Market Partner API — design contract only."""

    @property
    def source_name(self) -> str:
        return "yandex_market"

    def fetch_raw_observation(self, product_id: str) -> RawObservation:
        raise NotImplementedError(
            "Design contract only: runtime API calls disabled"
        )

    def _parse_payload_to_claims(
        self, payload: Dict[str, Any]
    ) -> List[Claim]:
        params = payload.get("parameterValues", [])
        attr_map = {
            "Материал": "material",
            "Ширина": "width_mm",
            "Высота": "height_mm",
            "Число дверей": "doors_count",
        }
        claims: List[Claim] = []

        for param in params:
            raw_name = param.get("name")
            raw_val = param.get("value")

            if raw_name in attr_map:
                claims.append(
                    Claim(
                        attribute_name=attr_map[raw_name],
                        value=raw_val,
                        status=(
                            ClaimStatus.OBSERVED
                            if raw_val is not None
                            else ClaimStatus.UNKNOWN
                        ),
                        raw_source_value=raw_val,
                        metadata={
                            "ym_param_id": param.get("parameterId")
                        },
                    )
                )

        return claims
```

## Provenance mapping contract

| JAMP attribute | Ozon source field | Wildberries source field | Yandex Market source field | Declarative value rule |
|---|---|---|---|---|
| `material` | `attributes[].name == "Материал"` | `options[].name == "Материал корпуса"` | `parameterValues[].name == "Материал"` | string normalization, e.g. `металл -> metal` |
| `width_mm` | `attributes[].name == "Ширина"` | `options[].name == "Ширина предмета"` | `parameterValues[].name == "Ширина"` | integer millimetres |
| `height_mm` | `attributes[].name == "Высота"` | `options[].name == "Высота предмета"` | `parameterValues[].name == "Высота"` | integer millimetres |
| `doors_count` | `attributes[].name == "Количество дверей"` | `options[].name == "Количество створок"` | `parameterValues[].name == "Число дверей"` | integer count |

Value normalization is a declared transformation boundary only. It does not
promote a claim to `VERIFIED`.

## Fail-closed invariants

1. Missing source field -> `UNKNOWN`; no default or guessed value.
2. Found source value -> `OBSERVED`; never `VERIFIED`.
3. Every emitted claim retains source provenance in `metadata`.
4. `raw_source_value` preserves the source-side value before normalization.
5. `RawObservation.raw_payload` remains the immutable external snapshot.
6. Source-specific parsing cannot call `EvidencePolicy` or qualification.
7. `fetch_raw_observation()` is a declared runtime boundary and is disabled
   for this design-only contract.
8. No confidence score or heuristic may determine a qualification verdict.

## Scope exclusions

- no marketplace network/API requests
- no credentials or secrets
- no runtime adapter implementation
- no tests or test fixtures
- no `.github/workflows/test.yml` changes
- no `src/jamp/run.py` changes
- no `EvidencePolicy` implementation
- no qualification implementation

## Repository invariants

- Base contract: `MarketplaceSourceAdapter v0.1.1`
- Base PR #258 HEAD: `73ed75327f860bc3df8e25a05c3757966f7eb46c`
- Git baseline: `dadf003e869f93446e5f8dc6cc8ef0c6dbd99247`
- Frozen Core: `src/jamp/run.py`
- Locked blob: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`
- Required Frozen Core delta: `0`
- `.github/workflows/test.yml`: delta `0`

## Status

`DESIGN-ONLY / PRE-IMPLEMENTATION`

Concrete adapter runtime implementation and terminal evidence require a
separate change.
