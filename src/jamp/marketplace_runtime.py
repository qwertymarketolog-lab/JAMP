from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from jamp.aew.contract import EvidenceRecord, EvidenceStatus
from jamp.aew.ledger import EvidenceLedger


class ParserStatus(StrEnum):
    OBSERVED = "OBSERVED"
    UNKNOWN = "UNKNOWN"


class QualificationVerdict(StrEnum):
    QUALIFIED = "QUALIFIED"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class RawObservation:
    observation_id: str
    marketplace: str
    source_locator: str
    observed_at: str
    retrieved_at: str | None
    raw_value: Mapping[str, Any]
    canonical_attribute: str
    normalized_value: Any
    status: EvidenceStatus

    @property
    def raw_hash(self) -> str:
        payload = json.dumps(
            self.raw_value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class Requirement:
    requirement_id: str
    attribute_name: str
    operator: str
    expected_value: Any
    required: bool = True


@dataclass(frozen=True)
class QualificationDecision:
    verdict: QualificationVerdict
    reason: str
    observation_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    decision_digest: str


class OfflineMarketplaceParser:
    """Minimal deterministic fixture parser; no network or provider calls."""

    def parse(self, fixture: Mapping[str, Any]) -> tuple[RawObservation, ...]:
        required = ("observation_id", "marketplace", "source_locator", "observed_at", "attributes")
        if any(key not in fixture for key in required):
            return ()

        observations: list[RawObservation] = []
        retrieved_at = fixture.get("retrieved_at")
        attributes = fixture["attributes"]
        if not isinstance(attributes, Mapping):
            return ()

        for attribute_name, value in attributes.items():
            status = ParserStatus.OBSERVED if value is not None else ParserStatus.UNKNOWN
            observations.append(
                RawObservation(
                    observation_id=f"{fixture['observation_id']}:{attribute_name}",
                    marketplace=str(fixture["marketplace"]),
                    source_locator=str(fixture["source_locator"]),
                    observed_at=str(fixture["observed_at"]),
                    retrieved_at=None if retrieved_at is None else str(retrieved_at),
                    raw_value={attribute_name: value},
                    canonical_attribute=str(attribute_name),
                    normalized_value=value,
                    status=status,
                )
            )
        return tuple(observations)


PolicyEvaluator = Callable[[Sequence[EvidenceRecord]], Sequence[EvidenceRecord]]


class MarketplaceQualificationRuntime:
    """Offline runtime for Marketplace → AEW → Qualification.

    Network transport and provider SDKs are deliberately absent. EvidencePolicy
    is injected as the only status-promotion boundary.
    """

    def __init__(self, policy: PolicyEvaluator) -> None:
        self._policy = policy
        self.ledger = EvidenceLedger()

    def run(
        self,
        observations: Sequence[RawObservation],
        requirements: Sequence[Requirement],
        *,
        task_id: str,
    ) -> QualificationDecision:
        if not observations or not requirements:
            return self._decision(QualificationVerdict.INCONCLUSIVE, "missing_input", (), ())

        records = tuple(self._to_evidence(o, task_id) for o in observations)
        evaluated = tuple(self._policy(records))
        if len(evaluated) != len(records):
            return self._decision(
                QualificationVerdict.INCONCLUSIVE, "policy_output_mismatch", observations, records
            )

        by_id = {record.evidence_id: record for record in evaluated}
        if set(by_id) != {record.evidence_id for record in records}:
            return self._decision(
                QualificationVerdict.INCONCLUSIVE, "policy_identity_mismatch", observations, records
            )

        for record in evaluated:
            self.ledger.append(record)

        verdict, reason = self._qualify(evaluated, requirements)
        snapshot = self.ledger.snapshot()
        return self._decision(verdict, reason, observations, snapshot)

    @staticmethod
    def _to_evidence(observation: RawObservation, task_id: str) -> EvidenceRecord:
        return EvidenceRecord(
            evidence_id=f"ev:{observation.observation_id}",
            task_id=task_id,
            claim_id=f"claim:{observation.observation_id}",
            source_type="marketplace observation",
            source_id=observation.observation_id,
            raw_hash=observation.raw_hash,
            observed_at=observation.observed_at,
            scope=observation.canonical_attribute,
            status=observation.status,
            metadata={
                "marketplace": observation.marketplace,
                "source_locator": observation.source_locator,
                "retrieved_at": observation.retrieved_at,
                "canonical_attribute": observation.canonical_attribute,
                "normalized_value": observation.normalized_value,
            },
        )

    @staticmethod
    def _qualify(
        records: Sequence[EvidenceRecord], requirements: Sequence[Requirement]
    ) -> tuple[QualificationVerdict, str]:
        verified = [
            record for record in records if record.status is EvidenceStatus.VERIFIED
        ]
        for requirement in requirements:
            matches = [
                record
                for record in verified
                if record.scope == requirement.attribute_name
            ]
            if not matches:
                if requirement.required:
                    return QualificationVerdict.INCONCLUSIVE, "required_evidence_missing"
                continue

            values = {record.metadata.get("normalized_value") for record in matches}
            if len(values) != 1:
                return QualificationVerdict.INCONCLUSIVE, "verified_conflict"

            if (
                not MarketplaceQualificationRuntime._matches(
                    next(iter(values)), requirement.operator, requirement.expected_value
                )
                and requirement.required
            ):
                return QualificationVerdict.INCONCLUSIVE, "requirement_mismatch"

        return QualificationVerdict.QUALIFIED, "all_required_requirements_satisfied"

    @staticmethod
    def _matches(value: Any, operator: str, expected: Any) -> bool:
        try:
            return {
                "EQUALS": value == expected,
                "NOT_EQUALS": value != expected,
                "GREATER_THAN": value > expected,
                "GREATER_OR_EQUAL": value >= expected,
                "LESS_THAN": value < expected,
                "LESS_OR_EQUAL": value <= expected,
            }[operator]
        except (KeyError, TypeError):
            return False

    @staticmethod
    def _decision(
        verdict: QualificationVerdict,
        reason: str,
        observations: Sequence[RawObservation],
        records: Sequence[EvidenceRecord],
    ) -> QualificationDecision:
        payload = {
            "verdict": verdict.value,
            "reason": reason,
            "observation_ids": sorted(o.observation_id for o in observations),
            "evidence_ids": sorted(r.evidence_id for r in records),
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return QualificationDecision(
            verdict=verdict,
            reason=reason,
            observation_ids=tuple(payload["observation_ids"]),
            evidence_ids=tuple(payload["evidence_ids"]),
            decision_digest=digest,
        )
