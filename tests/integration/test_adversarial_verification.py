"""Adversarial Verification Integration Test."""

from jamp.registry.candidates import Candidate, VerificationStatus
from jamp.engine.evaluate import VerificationEngine


def test_adversarial_4_way_split():
    knowledge_base = {
        "x > 0": True,
        "1 == 2": False,
    }

    engine = VerificationEngine(knowledge_base)

    candidates = [
        Candidate("C1", "x > 0", "source_ai_1"),
        Candidate("C2", "1 == 2", "source_ai_1"),
        Candidate("C3", "y == 5", "source_ai_1"),
        Candidate(
            "C4",
            "x > 0 AND x < 0",
            "source_ai_1",
            metadata={"is_contradictory": True},
        ),
    ]

    results = [engine.verify_candidate(c) for c in candidates]

    assert results[0].status == VerificationStatus.CONFIRMED
    assert results[1].status == VerificationStatus.REJECTED
    assert results[2].status == VerificationStatus.UNKNOWN
    assert results[3].status == VerificationStatus.CONFLICT

    assert results[0].provenance is not None
    assert results[0].provenance.source_id == "source_ai_1"
    assert results[0].provenance.rule_applied == "KB_EXACT_MATCH"
    assert results[0].provenance.event_id == "EVT_0001"
    assert len(results[0].provenance.fingerprint) == 64

    assert results[1].provenance is None
    assert results[2].provenance is None
    assert results[3].provenance is None
