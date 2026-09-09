from __future__ import annotations

import pytest

from jamp.research import evidence
from jamp.research import hypothesis_formation as hypothesis


def test_duplicate_evidence_refs_rejected():
    record = evidence.EvidenceRecord("a" * 64, "b" * 64, "c" * 64, 0)
    with pytest.raises(ValueError):
        hypothesis.Hypothesis(
            (record.evidence_hash, record.evidence_hash),
            record.state_hash,
            "observation implies structure",
            0,
        )
