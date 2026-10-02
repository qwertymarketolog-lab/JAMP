from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
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
    status: ParserStatus

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
class RequirementEvaluation:
    requirement_id: str
    required: bool
    operator: str
    expected_value: Any
    actual_value: Any
    evaluation_status: str
    evidence_ids: tuple[str, ...]
    evaluation_digest: str


@dataclass(frozen=True)
class DecisionAuditRecord:
    decision: "QualificationDecision"
    requirement_evaluations: tuple[RequirementEvaluation, ...]
    observation_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    evidence_digests: tuple[str, ...]
    decision_digest: str


@dataclass(frozen=True)
class QualificationDecision:
    decision_id: str
    decision_contract_version: str
    task_id: str
    subject_id: str
    requirement_set_hash: str
    evidence_scope_hash: str
    ledger_snapshot_id: str
    ledger_snapshot_digest: str
    checker_id: str
    checker_version: str
    checker_digest: str
    verdict: QualificationVerdict
    reason: str
    observation_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    evidence_digests: tuple[str, ...]
    requirement_evaluation_digests: tuple[str, ...]
    created_at: str
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
        self.audit_records: list[DecisionAuditRecord] = []

    def run(
        self,
        observations: Sequence[RawObservation],
        requirements: Sequence[Requirement],
        *,
        task_id: str,
        subject_id: str,
    ) -> QualificationDecision:
        if not observations or not requirements:
            return self._decision(
                QualificationVerdict.INCONCLUSIVE,
                "missing_input",
                (),
                (),
                task_id=task_id,
                subject_id=subject_id,
                requirements=requirements,
            evaluations=(),
            )

        records = tuple(self._to_evidence(o, task_id) for o in observations)
        evaluated = tuple(self._policy(records))
        if len(evaluated) != len(records):
            return self._decision(
                QualificationVerdict.INCONCLUSIVE,
                "policy_output_mismatch",
                observations,
                records,
                task_id=task_id,
                subject_id=subject_id,
                requirements=requirements,
            evaluations=(),
            )

        by_id = {record.evidence_id: record for record in evaluated}
        if set(by_id) != {record.evidence_id for record in records}:
            return self._decision(
                QualificationVerdict.INCONCLUSIVE,
                "policy_identity_mismatch",
                observations,
                records,
                task_id=task_id,
                subject_id=subject_id,
                requirements=requirements,
                evaluations=(),
            )

        for record in evaluated:
            self.ledger.append(record)

        verdict, reason, evaluations = self._qualify(evaluated, requirements)
        snapshot = self.ledger.snapshot()
        return self._decision(
            verdict,
            reason,
            observations,
            snapshot,
            task_id=task_id,
            subject_id=subject_id,
            requirements=requirements,
            evaluations=evaluations,
        )

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
            status=EvidenceStatus(observation.status.value),
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
    ) -> tuple[QualificationVerdict, str, tuple[RequirementEvaluation, ...]]:
        verified = [record for record in records if record.status is EvidenceStatus.VERIFIED]
        evaluations: list[RequirementEvaluation] = []
        for requirement in requirements:
            matches = [record for record in verified if record.scope == requirement.attribute_name]
            evidence_ids = tuple(sorted(record.evidence_id for record in matches))
            actual_value = None
            status = "INCONCLUSIVE"
            if matches:
                values = {record.metadata.get("normalized_value") for record in matches}
                if len(values) == 1:
                    actual_value = next(iter(values))
                    status = "SATISFIED" if MarketplaceQualificationRuntime._matches(actual_value, requirement.operator, requirement.expected_value) else "FAILED"
                else:
                    status = "INCONCLUSIVE"
            evaluation = RequirementEvaluation(
                requirement.requirement_id, requirement.required, requirement.operator,
                requirement.expected_value, actual_value, status, evidence_ids,
                MarketplaceQualificationRuntime._hash_json({
                    "requirement_id": requirement.requirement_id,
                    "required": requirement.required,
                    "operator": requirement.operator,
                    "expected_value": requirement.expected_value,
                    "actual_value": actual_value,
                    "evaluation_status": status,
                    "evidence_ids": evidence_ids,
                }),
            )
            evaluations.append(evaluation)
            if status == "INCONCLUSIVE" and requirement.required:
                return QualificationVerdict.INCONCLUSIVE, "required_evidence_missing", tuple(evaluations)
            if status == "FAILED" and requirement.required:
                return QualificationVerdict.INCONCLUSIVE, "requirement_mismatch", tuple(evaluations)
        return QualificationVerdict.QUALIFIED, "all_required_requirements_satisfied", tuple(evaluations)
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
    def _record_digest(record: EvidenceRecord) -> str:
        payload = {
            "evidence_id": record.evidence_id,
            "task_id": record.task_id,
            "claim_id": record.claim_id,
            "source_type": record.source_type,
            "source_id": record.source_id,
            "raw_hash": record.raw_hash,
            "observed_at": record.observed_at,
            "scope": record.scope,
            "status": record.status.value,
            "metadata": record.metadata,
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _hash_json(payload: Any) -> str:
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _decision(
        verdict: QualificationVerdict,
        reason: str,
        observations: Sequence[RawObservation],
        records: Sequence[EvidenceRecord],
        *,
        task_id: str,
        subject_id: str,
        requirements: Sequence[Requirement],
        evaluations: Sequence[RequirementEvaluation],
    ) -> QualificationDecision:
        evidence_digests = tuple(MarketplaceQualificationRuntime._record_digest(r) for r in records)
        observation_ids = tuple(sorted(o.observation_id for o in observations))
        evidence_ids = tuple(sorted(r.evidence_id for r in records))
        evaluation_digests = tuple(
            MarketplaceQualificationRuntime._hash_json(
                {"evidence_id": r.evidence_id, "scope": r.scope, "status": r.status.value}
            )
            for r in records
        )
        requirement_set_hash = MarketplaceQualificationRuntime._hash_json(
            [r.__dict__ for r in requirements]
        )
        evidence_scope_hash = MarketplaceQualificationRuntime._hash_json(
            list(zip(evidence_ids, evidence_digests, strict=True))
        )
        ledger_snapshot_digest = MarketplaceQualificationRuntime._hash_json(
            list(zip(evidence_ids, evidence_digests, strict=True))
        )
        ledger_snapshot_id = f"snapshot:{ledger_snapshot_digest}"
        checker_id = "jamp.marketplace.qualification"
        checker_version = "0.1"
        checker_digest = hashlib.sha256(b"jamp.marketplace.qualification:0.1").hexdigest()
        created_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        decision_id = f"decision:{task_id}:{created_at}"
        preimage = {
            "decision_contract_version": "0.1",
            "task_id": task_id,
            "subject_id": subject_id,
            "requirement_set_hash": requirement_set_hash,
            "evidence_scope_hash": evidence_scope_hash,
            "ledger_snapshot_id": ledger_snapshot_id,
            "ledger_snapshot_digest": ledger_snapshot_digest,
            "checker_id": checker_id,
            "checker_version": checker_version,
            "checker_digest": checker_digest,
            "decision_status": verdict.value,
            "created_at": created_at,
        }
        decision_digest = MarketplaceQualificationRuntime._hash_json(preimage)
        decision = QualificationDecision(
            decision_id,
            "0.1",
            task_id,
            subject_id,
            requirement_set_hash,
            evidence_scope_hash,
            ledger_snapshot_id,
            ledger_snapshot_digest,
            checker_id,
            checker_version,
            checker_digest,
            verdict,
            reason,
            observation_ids,
            evidence_ids,
            evidence_digests,
            evaluation_digests,
            created_at,
            decision_digest,
        )
        self.audit_records.append(
            DecisionAuditRecord(
                decision,
                tuple(evaluations),
                observation_ids,
                evidence_ids,
                evidence_digests,
                decision_digest,
            )
        )
        return decision
