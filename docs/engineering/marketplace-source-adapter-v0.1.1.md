# MarketplaceSourceAdapter v0.1.1 — Design Contract

## Purpose

This design-only contract defines an explicit boundary between marketplace
observation, evidence-policy evaluation, and deterministic qualification.

No marketplace API calls, runtime implementation, or CI workflow changes are
part of this contract.

## Pipeline

```
RawObservation
    |
    v
MarketplaceSourceAdapter.extract_claims()
    |
    v
Claims [OBSERVED | UNKNOWN]
    |
    v
EvidencePolicy.evaluate()
    |
    v
Claims [VERIFIED | UNKNOWN]
    |
    v
DeterministicQualificationEngine.qualify()
    |
    +-------------------+
    v                   v
QUALIFIED          INCONCLUSIVE
```

## Contract Types

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ClaimStatus(str, Enum):
    OBSERVED = "OBSERVED"
    VERIFIED = "VERIFIED"
    UNKNOWN = "UNKNOWN"


class QualificationVerdict(str, Enum):
    QUALIFIED = "QUALIFIED"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class RawObservation:
    observation_id: str
    source: str  # "ozon" | "wildberries" | "yandex_market"
    source_product_id: str
    source_url: Optional[str]
    observed_at: datetime
    retrieved_at: datetime
    raw_payload: Dict[str, Any]


@dataclass(frozen=True)
class Claim:
    attribute_name: str
    value: Any
    status: ClaimStatus
    raw_source_value: Optional[Any] = None
    metadata: Optional[Dict[str, Any]] = None


class MarketplaceSourceAdapter(ABC):
    """Layer 1: read-only data fetching and raw extraction."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        pass

    @abstractmethod
    def fetch_raw_observation(self, product_id: str) -> RawObservation:
        pass

    @abstractmethod
    def extract_claims(self, observation: RawObservation) -> List[Claim]:
        """Return claims restricted to OBSERVED or UNKNOWN."""
        pass


class EvidencePolicy(ABC):
    """Layer 2: the sole OBSERVED -> VERIFIED promotion boundary."""

    @abstractmethod
    def evaluate(self, claims: List[Claim]) -> List[Claim]:
        """
        Promote eligible OBSERVED claims to VERIFIED.
        UNKNOWN claims remain UNKNOWN.
        """
        pass


class DeterministicQualificationEngine(ABC):
    """Layer 3: fail-closed criteria evaluation."""

    @abstractmethod
    def qualify(
        self,
        verified_claims: List[Claim],
        requirements: Dict[str, Any],
    ) -> QualificationVerdict:
        """
        Evaluate requirements strictly against policy-evaluated claims.

        A required attribute passes only with a matching VERIFIED claim.
        UNKNOWN or non-VERIFIED required evidence yields INCONCLUSIVE.
        """
        pass
```

## Strict Invariants

1. **Adapter scope** — `MarketplaceSourceAdapter` MUST NOT emit
   `ClaimStatus.VERIFIED`. Extracted claims are only `OBSERVED` or
   `UNKNOWN`.
2. **Policy boundary** — `EvidencePolicy` is the sole contract component
   authorized to promote `OBSERVED -> VERIFIED`.
3. **Qualification boundary** — `DeterministicQualificationEngine` consumes
   claims only after EvidencePolicy evaluation and MUST NOT promote claims.
4. **Fail-closed** — a required criterion passes only when its value matches
   and its status is `VERIFIED`. Any required `UNKNOWN` or
   non-`VERIFIED` claim yields `INCONCLUSIVE`.
5. **No probabilistic decision rule** — `metadata` MAY carry provenance
   details such as confidence, but confidence MUST NOT determine the verdict.
6. **Observation integrity** — `RawObservation.raw_payload` is the immutable
   external snapshot; adapter extraction MUST NOT mutate or rewrite it.
7. **Timestamp separation** — `observed_at` identifies the source-side
   observation time; `retrieved_at` identifies JAMP retrieval time.
8. **API/runtime exclusion** — this document does not authorize real marketplace
   API calls or runtime adapter implementation.

## Evidence Semantics

The adapter is an observation mechanism, not a source of truth. The evidence
policy defines the conditions under which an observed claim can become
`VERIFIED`. Qualification is deterministic and operates only on
policy-evaluated evidence.

The same policy-evaluated claims MAY be qualified against multiple independent
requirement profiles without repeating the source API retrieval.

## Example Trace

```text
RawObservation(source=ozon, product_id=1409128412)
    -> material=metal [OBSERVED]
    -> doors_count=NULL [UNKNOWN]

EvidencePolicy
    -> material=metal [VERIFIED]
    -> doors_count=NULL [UNKNOWN]

Qualification(requirements={material: metal, doors_count: 2})
    -> INCONCLUSIVE
    -> missing_attributes=[doors_count]
```

## Repository Invariants

- Frozen Core: `src/jamp/run.py`
- Locked blob: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`
- Required Frozen Core delta: `0`
- `.github/workflows/test.yml`: no change
- Real marketplace API calls: none
- Runtime adapter implementation: none

## Scope

This is a design-only v0.1.1 contract. Implementation, schemas, concrete
Ozon/Wildberries/Yandex Market adapters, and runtime/API tests require separate
changes and terminal evidence.
