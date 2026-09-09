from jamp.research import hypothesis_formation as hypothesis
from tests.research.test_hypothesis_formation import P, STATE, _evidence
import pytest


def test_hypothesis_rejects_duplicate_evidence_refs():
    record = _evidence()
    with pytest.raises(ValueError, match="duplicate"):
        hypothesis.Hypothesis((record.evidence_hash, record.evidence_hash), STATE, P, 0)
