"""Research-only policy/tool boundary provenance for EXP-24.

This module records policy and tool-surface metadata without enforcing policy
or assigning semantic verdicts. It is deliberately isolated from src/jamp.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = "exp24.policy_boundary_observation.v0"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


@dataclass(frozen=True)
class PolicyBoundary:
    policy_id: str
    policy_version: str
    allowed_tools: tuple[str, ...]
    permissions: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class PolicyBoundaryObservation:
    observation_id: str
    schema_version: str
    source_ref: str
    attempt_index: int
    policy: PolicyBoundary
    provenance: dict[str, Any]
    immutable_hash: str


def policy_boundary_digest(
    *,
    source_ref: str,
    attempt_index: int,
    policy: PolicyBoundary,
    provenance: dict[str, Any],
    schema_version: str = SCHEMA_VERSION,
) -> str:
    envelope = {
        "schema_version": schema_version,
        "source_ref": source_ref,
        "attempt_index": attempt_index,
        "policy": {
            "policy_id": policy.policy_id,
            "policy_version": policy.policy_version,
            "allowed_tools": list(policy.allowed_tools),
            "permissions": [list(item) for item in policy.permissions],
        },
        "provenance": provenance,
    }
    return hashlib.sha256(canonical_bytes(envelope)).hexdigest()


def build_policy_boundary_observation(
    record: dict[str, Any],
) -> PolicyBoundaryObservation:
    policy_record = record["policy"]
    permissions = tuple(
        sorted(
            (str(tool), str(permission))
            for tool, permission in policy_record["permissions"].items()
        )
    )
    policy = PolicyBoundary(
        policy_id=policy_record["policy_id"],
        policy_version=policy_record["policy_version"],
        allowed_tools=tuple(sorted(set(policy_record["allowed_tools"]))),
        permissions=permissions,
    )
    provenance = dict(record["provenance"])
    digest = policy_boundary_digest(
        source_ref=record["source_ref"],
        attempt_index=record["attempt_index"],
        policy=policy,
        provenance=provenance,
    )
    return PolicyBoundaryObservation(
        observation_id=digest,
        schema_version=SCHEMA_VERSION,
        source_ref=record["source_ref"],
        attempt_index=record["attempt_index"],
        policy=policy,
        provenance=provenance,
        immutable_hash=digest,
    )
