"""P18.3 controlled cross-task pattern transfer.

This module is deliberately non-heuristic.  It does not decide whether a
pattern is useful; it only verifies authorization, ownership, provenance and
cryptographic integrity before producing a detached target-family projection.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping


_DIGEST_FIELD = "projection_digest"


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _require_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class TransferAuthorization:
    """Cryptographically bound authorization for one A -> B transfer."""

    authorization_id: str
    source_family: str
    target_family: str
    source_digest: str
    provenance: Mapping[str, Any]
    policy_reason: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "TransferAuthorization":
        if not isinstance(value, Mapping):
            raise TypeError("authorization must be a mapping")
        required = (
            "authorization_id",
            "source_family",
            "target_family",
            "source_digest",
            "provenance",
            "policy_reason",
        )
        missing = [field for field in required if field not in value]
        if missing:
            raise ValueError(f"authorization missing fields: {', '.join(missing)}")
        source_digest = value["source_digest"]
        if not isinstance(source_digest, str) or len(source_digest) != 64:
            raise ValueError("authorization source_digest must be a SHA-256 hex digest")
        try:
            int(source_digest, 16)
        except ValueError as exc:
            raise ValueError("authorization source_digest must be hexadecimal") from exc
        if not isinstance(value["provenance"], Mapping):
            raise TypeError("authorization provenance must be a mapping")
        return cls(
            authorization_id=_require_nonempty_string(value["authorization_id"], "authorization_id"),
            source_family=_require_nonempty_string(value["source_family"], "source_family"),
            target_family=_require_nonempty_string(value["target_family"], "target_family"),
            source_digest=source_digest,
            provenance=deepcopy(dict(value["provenance"])),
            policy_reason=_require_nonempty_string(value["policy_reason"], "policy_reason"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "authorization_id": self.authorization_id,
            "source_family": self.source_family,
            "target_family": self.target_family,
            "source_digest": self.source_digest,
            "provenance": deepcopy(dict(self.provenance)),
            "policy_reason": self.policy_reason,
        }

    @property
    def authorization_token(self) -> str:
        """Deterministic token binding the complete authorization envelope."""
        return _digest(self.to_dict())


@dataclass(frozen=True, slots=True)
class TransferRecord:
    """Immutable provenance model for one verified transfer."""

    authorization_id: str
    authorization_token: str
    source_family: str
    target_family: str
    source_digest: str
    projection_digest: str
    provenance: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "authorization_id": self.authorization_id,
            "authorization_token": self.authorization_token,
            "source_family": self.source_family,
            "target_family": self.target_family,
            "source_digest": self.source_digest,
            "projection_digest": self.projection_digest,
            "provenance": deepcopy(dict(self.provenance)),
        }


class ControlledTransfer:
    """Fail-closed gateway for explicitly authorized cross-task projection."""

    def __init__(self, target_family: str) -> None:
        self.target_family = _require_nonempty_string(target_family, "target_family")

    @staticmethod
    def _source_digest(source_pattern: Mapping[str, Any]) -> str:
        return _digest(dict(source_pattern))

    @staticmethod
    def _unsigned_projection(record: Mapping[str, Any]) -> dict[str, Any]:
        unsigned = deepcopy(dict(record))
        unsigned[_DIGEST_FIELD] = None
        return unsigned

    @classmethod
    def _projection_digest(cls, record: Mapping[str, Any]) -> str:
        return _digest(cls._unsigned_projection(record))

    def _validate_authorization(
        self,
        source_pattern: Mapping[str, Any],
        authorization: TransferAuthorization,
    ) -> None:
        source_family = source_pattern.get("family_id", source_pattern.get("task_family"))
        if source_family != authorization.source_family:
            raise ValueError("authorization source family does not own source pattern")
        if authorization.target_family != self.target_family:
            raise PermissionError("authorization is bound to a different target family")
        if authorization.source_digest != self._source_digest(source_pattern):
            raise PermissionError("authorization source digest does not match source pattern")
        if authorization.source_family == authorization.target_family:
            raise ValueError("controlled transfer requires distinct source and target families")

    def _validate_projection(
        self,
        source_pattern: Mapping[str, Any],
        authorization: TransferAuthorization,
        projection: Mapping[str, Any],
    ) -> None:
        target_family = projection.get("family_id", projection.get("task_family"))
        if target_family != self.target_family:
            raise PermissionError("projection target family does not match gateway")
        if target_family != authorization.target_family:
            raise PermissionError("projection target family does not match authorization")
        if projection is source_pattern:
            raise ValueError("projection must be independently owned")
        payload = projection.get("payload")
        source_payload = source_pattern.get("payload")
        if payload is source_payload:
            raise ValueError("projection shares mutable payload with source")
        provenance = projection.get("provenance")
        if not isinstance(provenance, Mapping):
            raise ValueError("projection provenance is required")
        if provenance.get("source_ref") is not None:
            raise ValueError("shared source references are forbidden")
        if provenance.get("source_digest") != authorization.source_digest:
            raise ValueError("projection provenance source digest mismatch")
        if provenance.get("authorization_id") != authorization.authorization_id:
            raise ValueError("projection provenance authorization mismatch")

    def transfer(
        self,
        *,
        source_pattern: Mapping[str, Any],
        authorization: Mapping[str, Any] | TransferAuthorization | None,
        projection: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Authorize and seal a detached projection owned exclusively by target."""
        if not isinstance(source_pattern, Mapping):
            raise TypeError("source_pattern must be a mapping")
        if not isinstance(projection, Mapping):
            raise TypeError("projection must be a mapping")
        if authorization is None:
            raise PermissionError("explicit transfer authorization is required")

        auth = authorization if isinstance(authorization, TransferAuthorization) else TransferAuthorization.from_mapping(authorization)
        self._validate_authorization(source_pattern, auth)
        self._validate_projection(source_pattern, auth, projection)

        result = deepcopy(dict(projection))
        result["authorization_id"] = auth.authorization_id
        result["authorization_token"] = auth.authorization_token
        result["source_family"] = auth.source_family
        result["target_family"] = auth.target_family
        result["source_digest"] = auth.source_digest
        result["provenance"] = deepcopy(dict(result["provenance"]))
        result["provenance"]["authorization_token"] = auth.authorization_token
        result[_DIGEST_FIELD] = None
        result[_DIGEST_FIELD] = self._projection_digest(result)
        return result

    def verify_transfer(self, record: Mapping[str, Any]) -> bool:
        """Verify the sealed projection without mutating or re-projecting it."""
        if not isinstance(record, Mapping):
            return False
        digest = record.get(_DIGEST_FIELD)
        if not isinstance(digest, str):
            return False
        if record.get("target_family") != self.target_family:
            return False
        try:
            return digest == self._projection_digest(record)
        except (TypeError, ValueError):
            return False

    def projection_digest(self, record: Mapping[str, Any]) -> str:
        """Return the canonical digest of a sealed or candidate projection."""
        if not isinstance(record, Mapping):
            raise TypeError("transfer record must be a mapping")
        return self._projection_digest(record)

    def replay(self, record: Mapping[str, Any]) -> dict[str, Any]:
        """Verify an existing transfer record before exposing its detached copy."""
        if not self.verify_transfer(record):
            raise PermissionError("transfer record integrity verification failed")
        authorization_id = record.get("authorization_id")
        token = record.get("authorization_token")
        provenance = record.get("provenance")
        if not isinstance(authorization_id, str) or not isinstance(token, str):
            raise ValueError("transfer record authorization metadata is incomplete")
        if not isinstance(provenance, Mapping):
            raise ValueError("transfer record provenance is incomplete")
        if provenance.get("authorization_id") != authorization_id:
            raise PermissionError("transfer record authorization lineage mismatch")
        if provenance.get("authorization_token") != token:
            raise PermissionError("transfer record authorization token mismatch")
        return deepcopy(dict(record))

    def record(self, transfer: Mapping[str, Any]) -> TransferRecord:
        """Materialize immutable provenance telemetry from a verified transfer."""
        if not self.verify_transfer(transfer):
            raise ValueError("cannot record an invalid transfer")
        return TransferRecord(
            authorization_id=transfer["authorization_id"],
            authorization_token=transfer["authorization_token"],
            source_family=transfer["source_family"],
            target_family=transfer["target_family"],
            source_digest=transfer["source_digest"],
            projection_digest=transfer[_DIGEST_FIELD],
            provenance=deepcopy(dict(transfer["provenance"])),
        )


__all__ = ["ControlledTransfer", "TransferAuthorization", "TransferRecord"]
