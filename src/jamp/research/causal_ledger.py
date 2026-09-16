"""EXP-10 / R0.5 append-only causal ledger.

The ledger is a local, deterministic integrity layer. It binds events into a
single append-only hash chain; it does not claim external existence or time.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .canonical import replay_hash

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
ZERO_HASH = "0" * 64


class LedgerError(ValueError):
    """Base error for rejected causal-ledger operations."""

    code = "LEDGER_ERROR"


class GenesisViolationError(LedgerError):
    code = "GENESIS_VIOLATION"


class ParentMissingError(LedgerError):
    code = "PARENT_MISSING"


class NonHeadParentError(LedgerError):
    code = "NON_HEAD_PARENT"


class PayloadHashMismatchError(LedgerError):
    code = "PAYLOAD_HASH_MISMATCH"


class EventHashMismatchError(LedgerError):
    code = "EVENT_HASH_MISMATCH"


class SequenceDiscontinuityError(LedgerError):
    code = "SEQUENCE_DISCONTINUITY"


class HeadViolationError(LedgerError):
    code = "HEAD_VIOLATION"


class DuplicateEventError(LedgerError):
    code = "DUPLICATE_EVENT"


class CausalOrderViolationError(LedgerError):
    code = "CAUSAL_ORDER_VIOLATION"


class ExecutionIdDuplicateError(LedgerError):
    code = "EXECUTION_ID_DUPLICATE"


class PredictionCommitMissingError(LedgerError):
    code = "PREDICTION_COMMIT_MISSING"


class ExecutionStartMissingError(LedgerError):
    code = "EXECUTION_START_MISSING"


class ExecutionResultDuplicateError(LedgerError):
    code = "EXECUTION_RESULT_DUPLICATE"


class EvidenceDuplicateError(LedgerError):
    code = "EVIDENCE_DUPLICATE"


class ExecutionResultMissingError(LedgerError):
    code = "EXECUTION_RESULT_MISSING"


class EventTypeV0(str, Enum):  # noqa: UP042
    GENESIS = "GENESIS"
    PREDICTION_COMMIT = "PREDICTION_COMMIT"
    EXECUTION_START = "EXECUTION_START"
    EXECUTION_RESULT = "EXECUTION_RESULT"
    EVIDENCE_RECORD = "EVIDENCE_RECORD"


@dataclass(frozen=True, slots=True)
class PredictionCommitV0:
    """R0.2 payload linking the ledger to an immutable PredictionRecord."""

    prediction_hash: str

    def __post_init__(self) -> None:
        _validate_hash(self.prediction_hash, "prediction_hash")

    def canonical_payload(self) -> dict[str, str]:
        return {"prediction_hash": self.prediction_hash}


@dataclass(frozen=True, slots=True)
class ExecutionStartV0:
    """R0.3 payload binding execution identity to a PredictionCommit event."""

    prediction_commit_hash: str
    execution_id: str

    def __post_init__(self) -> None:
        _validate_hash(self.prediction_commit_hash, "prediction_commit_hash")
        if not isinstance(self.execution_id, str) or not self.execution_id.strip():
            raise LedgerError("execution_id must be a non-empty string")

    def canonical_payload(self) -> dict[str, str]:
        return {
            "execution_id": self.execution_id,
            "prediction_commit_hash": self.prediction_commit_hash,
        }


@dataclass(frozen=True, slots=True)
class ExecutionResultV0:
    """R0.4 payload binding a result reference to an ExecutionStart event."""

    execution_start_hash: str
    result_ref: str

    def __post_init__(self) -> None:
        _validate_hash(self.execution_start_hash, "execution_start_hash")
        _validate_hash(self.result_ref, "result_ref")

    def canonical_payload(self) -> dict[str, str]:
        return {
            "execution_start_hash": self.execution_start_hash,
            "result_ref": self.result_ref,
        }


@dataclass(frozen=True, slots=True)
class EvidenceRecordV0:
    """R0.5 payload binding an evidence artifact to an ExecutionResult event."""

    execution_result_hash: str
    evidence_ref: str

    def __post_init__(self) -> None:
        _validate_hash(self.execution_result_hash, "execution_result_hash")
        _validate_hash(self.evidence_ref, "evidence_ref")

    def canonical_payload(self) -> dict[str, str]:
        return {
            "execution_result_hash": self.execution_result_hash,
            "evidence_ref": self.evidence_ref,
        }


@dataclass(frozen=True, slots=True)
class CausalEventV0:
    """Immutable hash-chained event envelope defined by R0.2."""

    event_type: EventTypeV0
    event_version: str
    sequence_index: int
    parent_hash: str
    payload_hash: str
    event_hash: str

    def __post_init__(self) -> None:
        try:
            event_type = EventTypeV0(self.event_type)
        except ValueError as exc:
            raise LedgerError("invalid event_type") from exc
        object.__setattr__(self, "event_type", event_type)
        if self.event_version != "0":
            raise LedgerError("event_version must be '0'")
        if (
            not isinstance(self.sequence_index, int)
            or isinstance(self.sequence_index, bool)
            or self.sequence_index < 0
        ):
            raise LedgerError("sequence_index must be a non-negative integer")
        _validate_hash(self.parent_hash, "parent_hash")
        _validate_hash(self.payload_hash, "payload_hash")
        _validate_hash(self.event_hash, "event_hash")

    def hash_material(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "event_version": self.event_version,
            "parent_hash": self.parent_hash,
            "payload_hash": self.payload_hash,
            "sequence_index": self.sequence_index,
        }

    def verify_event_hash(self) -> bool:
        return replay_hash(self.hash_material()) == self.event_hash


@dataclass(frozen=True, slots=True)
class LedgerSnapshot:
    """Read-only ledger state useful for atomicity assertions."""

    head: str
    event_count: int


class CausalLedger:
    """Single-head, append-only causal ledger for EXP-10 R0.5."""

    def __init__(self) -> None:
        self._events: dict[str, CausalEventV0] = {}
        self._head = ZERO_HASH
        self._execution_ids: set[str] = set()
        self._execution_result_starts: set[str] = set()
        self._evidence_results: set[str] = set()

    @property
    def head(self) -> str:
        return self._head

    @property
    def event_count(self) -> int:
        return len(self._events)

    def snapshot(self) -> LedgerSnapshot:
        return LedgerSnapshot(self._head, len(self._events))

    def get(self, event_hash: str) -> CausalEventV0 | None:
        return self._events.get(event_hash)

    @staticmethod
    def payload_hash(payload: Mapping[str, Any]) -> str:
        return replay_hash(dict(payload))

    @staticmethod
    def build_event(
        event_type: EventTypeV0,
        sequence_index: int,
        parent_hash: str,
        payload: Mapping[str, Any],
    ) -> CausalEventV0:
        payload_hash = replay_hash(dict(payload))
        material = {
            "event_type": EventTypeV0(event_type).value,
            "event_version": "0",
            "parent_hash": parent_hash,
            "payload_hash": payload_hash,
            "sequence_index": sequence_index,
        }
        return CausalEventV0(
            event_type=EventTypeV0(event_type),
            event_version="0",
            sequence_index=sequence_index,
            parent_hash=parent_hash,
            payload_hash=payload_hash,
            event_hash=replay_hash(material),
        )

    @classmethod
    def genesis(cls) -> CausalEventV0:
        return cls.build_event(EventTypeV0.GENESIS, 0, ZERO_HASH, {})

    def append_genesis(self) -> CausalEventV0:
        return self.append(self.genesis(), payload={})

    def append_prediction_commit(self, prediction_hash: str) -> CausalEventV0:
        payload = PredictionCommitV0(prediction_hash).canonical_payload()
        return self.append(
            self.build_event(
                EventTypeV0.PREDICTION_COMMIT,
                len(self._events),
                self._head,
                payload,
            ),
            payload=payload,
        )

    def append_execution_start(
        self,
        prediction_commit_hash: str,
        execution_id: str,
    ) -> CausalEventV0:
        payload_model = ExecutionStartV0(
            prediction_commit_hash=prediction_commit_hash,
            execution_id=execution_id,
        )
        if execution_id in self._execution_ids:
            raise ExecutionIdDuplicateError("execution_id already exists")
        payload = payload_model.canonical_payload()
        return self.append(
            self.build_event(
                EventTypeV0.EXECUTION_START,
                len(self._events),
                self._head,
                payload,
            ),
            payload=payload,
        )

    def append_execution_result(
        self,
        execution_start_hash: str,
        result_ref: str,
    ) -> CausalEventV0:
        payload_model = ExecutionResultV0(
            execution_start_hash=execution_start_hash,
            result_ref=result_ref,
        )
        if execution_start_hash in self._execution_result_starts:
            raise ExecutionResultDuplicateError("execution result already exists")
        payload = payload_model.canonical_payload()
        return self.append(
            self.build_event(
                EventTypeV0.EXECUTION_RESULT,
                len(self._events),
                self._head,
                payload,
            ),
            payload=payload,
        )

    def append_evidence_record(
        self,
        execution_result_hash: str,
        evidence_ref: str,
    ) -> CausalEventV0:
        payload_model = EvidenceRecordV0(
            execution_result_hash=execution_result_hash,
            evidence_ref=evidence_ref,
        )
        if execution_result_hash in self._evidence_results:
            raise EvidenceDuplicateError("evidence record already exists")
        payload = payload_model.canonical_payload()
        return self.append(
            self.build_event(
                EventTypeV0.EVIDENCE_RECORD,
                len(self._events),
                self._head,
                payload,
            ),
            payload=payload,
        )

    def append(self, event: CausalEventV0, *, payload: Mapping[str, Any]) -> CausalEventV0:
        """Validate every condition before mutating state (L0)."""
        self._validate(event, payload)
        self._events[event.event_hash] = event
        if event.event_type is EventTypeV0.EXECUTION_START:
            execution_start = ExecutionStartV0(**dict(payload))
            self._execution_ids.add(execution_start.execution_id)
        elif event.event_type is EventTypeV0.EXECUTION_RESULT:
            execution_result = ExecutionResultV0(**dict(payload))
            self._execution_result_starts.add(execution_result.execution_start_hash)
        elif event.event_type is EventTypeV0.EVIDENCE_RECORD:
            evidence = EvidenceRecordV0(**dict(payload))
            self._evidence_results.add(evidence.execution_result_hash)
        self._head = event.event_hash
        return event

    def _validate(self, event: CausalEventV0, payload: Mapping[str, Any]) -> None:
        if event.event_hash in self._events:
            raise DuplicateEventError("event already exists")
        if not event.verify_event_hash():
            raise EventHashMismatchError("event_hash does not match canonical event material")
        actual_payload_hash = replay_hash(dict(payload))
        if actual_payload_hash != event.payload_hash:
            raise PayloadHashMismatchError("payload_hash does not match canonical payload")

        if not self._events:
            if event.event_type is not EventTypeV0.GENESIS:
                raise GenesisViolationError("first event must be GENESIS")
            if event.sequence_index != 0 or event.parent_hash != ZERO_HASH:
                raise GenesisViolationError("GENESIS must have sequence 0 and zero parent")
            return

        if event.event_type is EventTypeV0.GENESIS:
            raise GenesisViolationError("GENESIS may occur only once")
        if event.parent_hash not in self._events:
            raise ParentMissingError("parent_hash is not present in the ledger")
        if event.parent_hash != self._head:
            raise HeadViolationError("event must extend the current ledger head")
        if event.sequence_index != self._events[self._head].sequence_index + 1:
            raise SequenceDiscontinuityError("sequence_index must follow the current head")

        parent_type = self._events[self._head].event_type
        expected = {
            EventTypeV0.GENESIS: EventTypeV0.PREDICTION_COMMIT,
            EventTypeV0.PREDICTION_COMMIT: EventTypeV0.EXECUTION_START,
            EventTypeV0.EXECUTION_START: EventTypeV0.EXECUTION_RESULT,
            EventTypeV0.EXECUTION_RESULT: EventTypeV0.EVIDENCE_RECORD,
        }
        if parent_type is EventTypeV0.EVIDENCE_RECORD:
            raise CausalOrderViolationError("event type violates the R0.2 causal order")
        if event.event_type is EventTypeV0.EXECUTION_START:
            if parent_type is not EventTypeV0.PREDICTION_COMMIT:
                raise PredictionCommitMissingError(
                    "execution_start requires a PREDICTION_COMMIT parent"
                )
            execution_start = ExecutionStartV0(**dict(payload))
            if execution_start.prediction_commit_hash != event.parent_hash:
                raise PredictionCommitMissingError(
                    "execution_start must bind to its immediate prediction commit parent"
                )
            if execution_start.execution_id in self._execution_ids:
                raise ExecutionIdDuplicateError("execution_id already exists")
        elif event.event_type is EventTypeV0.EXECUTION_RESULT:
            if parent_type is not EventTypeV0.EXECUTION_START:
                raise ExecutionStartMissingError(
                    "execution_result requires an EXECUTION_START parent"
                )
            execution_result = ExecutionResultV0(**dict(payload))
            if execution_result.execution_start_hash != event.parent_hash:
                raise ExecutionStartMissingError(
                    "execution_result must bind to its immediate execution start parent"
                )
            if execution_result.execution_start_hash in self._execution_result_starts:
                raise ExecutionResultDuplicateError("execution result already exists")
        elif event.event_type is EventTypeV0.EVIDENCE_RECORD:
            if "execution_result_hash" not in payload or "evidence_ref" not in payload:
                raise CausalOrderViolationError("event type violates the R0.2 causal order")
            if parent_type is not EventTypeV0.EXECUTION_RESULT:
                raise ExecutionResultMissingError(
                    "evidence_record requires an EXECUTION_RESULT parent"
                )
            evidence = EvidenceRecordV0(**dict(payload))
            if evidence.execution_result_hash != event.parent_hash:
                raise ExecutionResultMissingError(
                    "evidence_record must bind to its immediate execution result parent"
                )
            if evidence.execution_result_hash in self._evidence_results:
                raise EvidenceDuplicateError("evidence record already exists")
        elif event.event_type is not expected[parent_type]:
            raise CausalOrderViolationError("event type violates the R0.2 causal order")


def _validate_hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise LedgerError(f"{field} must be lowercase SHA-256")
    return value


__all__ = (
    "CausalEventV0",
    "CausalLedger",
    "CausalOrderViolationError",
    "DuplicateEventError",
    "EventHashMismatchError",
    "EventTypeV0",
    "EvidenceDuplicateError",
    "EvidenceRecordV0",
    "ExecutionIdDuplicateError",
    "ExecutionResultDuplicateError",
    "ExecutionResultMissingError",
    "ExecutionResultV0",
    "ExecutionStartMissingError",
    "ExecutionStartV0",
    "GenesisViolationError",
    "HeadViolationError",
    "LedgerError",
    "LedgerSnapshot",
    "NonHeadParentError",
    "ParentMissingError",
    "PayloadHashMismatchError",
    "PredictionCommitMissingError",
    "PredictionCommitV0",
    "SequenceDiscontinuityError",
    "ZERO_HASH",
)
