"""EXP-11 research-only tests for EvidenceRecordV0 event binding."""

from __future__ import annotations

import pytest

from jamp.research.canonical import replay_hash
from tests.research.test_evidence_record_v0 import EXPECTED_HASH, V0_001


def test_t1_evidence_binding_is_deterministic() -> None:
    ref_a = replay_hash(V0_001)
    ref_b = replay_hash(V0_001)
    ref_c = replay_hash(dict(V0_001))

    assert ref_a == EXPECTED_HASH
    assert ref_b == EXPECTED_HASH
    assert ref_c == EXPECTED_HASH


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("payload", {"value": 43, "unit": "count"}),
        ("source_ref", "artifact:example-002"),
        ("observed_at", "2026-09-16T16:00:01Z"),
    ],
)
def test_t2_semantic_change_changes_evidence_ref(
    field: str, value: object
) -> None:
    modified = dict(V0_001)
    modified[field] = value

    assert replay_hash(modified) != EXPECTED_HASH
