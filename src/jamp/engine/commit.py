"""JAMP Authoritative Commit Gateway.

Registry mutations are authorized only through this controller, and every
state transition receives a corresponding Event DAG event.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jamp.events.dag import EventDAG
from jamp.registry.candidates import VerificationResult, VerificationStatus
from jamp.registry.registry import Registry, RegistryRecord


class UnauthorizedCommitError(Exception):
    """Raised when a verified result cannot be authorized for commit."""


@dataclass(frozen=True)
class CommitReceipt:
    event_id: str
    state_fingerprint: str
    status: VerificationStatus


class CommitManager:
    """The sole authorized controller for Registry state mutation."""

    def __init__(self, registry: Registry, dag: EventDAG):
        self._registry = registry
        self._dag = dag
        self._registry_token = registry._commit_authority()

    def commit(self, verification_result: VerificationResult) -> CommitReceipt:
        candidate = verification_result.candidate
        status = verification_result.status

        payload: dict[str, Any] = {
            "candidate_id": candidate.candidate_id,
            "statement": candidate.statement,
            "status": status.value,
        }

        if status == VerificationStatus.CONFIRMED:
            provenance = verification_result.provenance
            if provenance is None:
                raise UnauthorizedCommitError(
                    "CONFIRMED status requires complete Provenance."
                )

            provenance_payload = provenance.__dict__.copy()
            payload["provenance"] = provenance_payload
            record = RegistryRecord(
                record_id=f"FACT_{candidate.candidate_id}",
                kind="fact",
                payload={
                    "candidate_id": candidate.candidate_id,
                    "statement": candidate.statement,
                    "source_id": candidate.source_id,
                    "provenance": provenance_payload,
                },
            )
            event_node = self._dag.append_event("FactCommitted", payload)
            self._registry._commit_add(record, self._registry_token)

        elif status == VerificationStatus.CONFLICT:
            record = RegistryRecord(
                record_id=f"CONFLICT_{candidate.candidate_id}",
                kind="conflict",
                payload={
                    "candidate_id": candidate.candidate_id,
                    "statement": candidate.statement,
                },
            )
            event_node = self._dag.append_event("ConflictDetected", payload)
            self._registry._commit_add(record, self._registry_token)

        elif status == VerificationStatus.REJECTED:
            event_node = self._dag.append_event("FactRejected", payload)

        elif status == VerificationStatus.UNKNOWN:
            event_node = self._dag.append_event("FactUnverified", payload)

        else:
            raise ValueError(f"Unhandled verification status: {status}")

        return CommitReceipt(
            event_id=event_node.event_id,
            state_fingerprint=event_node.hash,
            status=status,
        )
