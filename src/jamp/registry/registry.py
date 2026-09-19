"""Append-only registry with an authoritative commit boundary."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class UnauthorizedRegistryMutation(Exception):
    """Raised when Registry mutation is attempted outside the commit gateway."""


@dataclass(frozen=True)
class RegistryRecord:
    record_id: str
    kind: str
    payload: dict[str, Any]


class Registry:
    def __init__(self) -> None:
        self._records: list[RegistryRecord] = []
        self._commit_token = object()

    def add(self, record: RegistryRecord) -> None:
        """Reject direct state mutation; CommitManager is the write gateway."""
        raise UnauthorizedRegistryMutation(
            "Registry mutation is only authorized through CommitManager.commit()."
        )

    def _commit_authority(self) -> object:
        """Return the opaque capability used internally by CommitManager."""
        return self._commit_token

    def _commit_add(self, record: RegistryRecord, token: object) -> None:
        """Apply an authorized registry mutation."""
        if token is not self._commit_token:
            raise UnauthorizedRegistryMutation("Invalid Registry commit authority.")
        if any(r.record_id == record.record_id for r in self._records):
            raise ValueError(f"Duplicate record_id: {record.record_id}")
        self._records.append(record)

    def all(self) -> tuple[RegistryRecord, ...]:
        return tuple(self._records)

    def by_kind(self, kind: str) -> tuple[RegistryRecord, ...]:
        return tuple(r for r in self._records if r.kind == kind)

    @property
    def facts(self) -> frozenset[str]:
        """Compatibility view of committed fact statements."""
        return frozenset(
            record.payload["statement"]
            for record in self.by_kind("fact")
            if "statement" in record.payload
        )

    @property
    def metadata(self) -> dict[str, Any]:
        """Compatibility view of conflict metadata."""
        return {
            f"conflict_{record.payload['candidate_id']}": record.payload["statement"]
            for record in self.by_kind("conflict")
            if "candidate_id" in record.payload and "statement" in record.payload
        }
