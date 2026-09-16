"""EXP-11 research-only tests for EvidenceRecordV0 event binding."""

from __future__ import annotations

from jamp.research.canonical import replay_hash
from tests.research.test_evidence_record_v0 import EXPECTED_HASH, V0_001


def test_t1_evidence_binding_is_deterministic() -> None:
    ref_a = replay_hash(V0_001)
    ref_b = replay_hash(V0_001)
    ref_c = replay_hash(dict(V0_001))

    assert ref_a == EXPECTED_HASH
    assert ref_b == EXPECTED_HASH
    assert ref_c == EXPECTED_HASH
