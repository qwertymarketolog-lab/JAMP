"""EXP-10 research-only tests for EvidenceRecordV0.

These tests intentionally do not add a production EvidenceRecord API.
They exercise the existing P19.1 canonicalization primitive and a local
V0 schema boundary.
"""

from __future__ import annotations

import pytest

from jamp.research.canonical import canonical_bytes, replay_hash


V0_001 = {
    "evidence_type": "observation",
    "payload": {"value": 42, "unit": "count"},
    "source_ref": "artifact:example-001",
    "observed_at": "2026-09-16T16:00:00Z",
}

EXPECTED_CANONICAL = (
    b'{"evidence_type":"observation","observed_at":"2026-09-16T16:00:00Z",'
    b'"payload":{"unit":"count","value":42},"source_ref":"artifact:example-001"}'
)
EXPECTED_HASH = "c791c27c173d351847da161648ba2ebaae3626223d43c6115294913c69e98085"

ALLOWED_FIELDS = frozenset(
    {"evidence_type", "payload", "source_ref", "observed_at"}
)
FORBIDDEN_FIELDS = frozenset({"interpretation", "claim", "confidence"})


def _validate_v0(record: dict[str, object]) -> None:
    unknown = set(record) - ALLOWED_FIELDS
    if unknown:
        raise ValueError(f"EvidenceRecordV0 rejects unknown fields: {sorted(unknown)}")
    missing = ALLOWED_FIELDS - set(record)
    if missing:
        raise ValueError(f"EvidenceRecordV0 missing required fields: {sorted(missing)}")


def test_t1_v0_001_is_deterministic() -> None:
    _validate_v0(V0_001)
    assert canonical_bytes(V0_001) == EXPECTED_CANONICAL
    assert replay_hash(V0_001) == EXPECTED_HASH
    assert replay_hash(dict(V0_001)) == EXPECTED_HASH


@pytest.mark.parametrize("field", ["evidence_type", "payload", "source_ref", "observed_at"])
def test_t2_semantic_field_change_changes_hash(field: str) -> None:
    _validate_v0(V0_001)
    modified = dict(V0_001)
    if field == "evidence_type":
        modified[field] = "measurement"
    elif field == "payload":
        modified[field] = {"value": 43, "unit": "count"}
    elif field == "source_ref":
        modified[field] = "artifact:example-002"
    else:
        modified[field] = "2026-09-16T16:00:01Z"
    _validate_v0(modified)
    assert replay_hash(modified) != EXPECTED_HASH


@pytest.mark.parametrize("field", sorted(FORBIDDEN_FIELDS))
def test_t3_forbidden_interpretive_fields_are_rejected(field: str) -> None:
    invalid = dict(V0_001)
    invalid[field] = "forbidden"
    with pytest.raises(ValueError, match="rejects unknown fields"):
        _validate_v0(invalid)


def test_t4_ledger_boundary_uses_ref_not_payload() -> None:
    _validate_v0(V0_001)
    evidence_ref = replay_hash(V0_001)
    ledger_binding = {"evidence_ref": evidence_ref}

    assert ledger_binding == {"evidence_ref": EXPECTED_HASH}
    assert "payload" not in ledger_binding
    assert "interpretation" not in ledger_binding
