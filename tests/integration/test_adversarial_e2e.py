"""End-to-End Adversarial Verification, Commit Gateway & Event DAG Test."""

from jamp.engine.pipeline import JAMPPipeline
from jamp.registry.candidates import Candidate, VerificationStatus


def test_adversarial_end_to_end_dag():
    kb = {"a == a": True, "0 == 1": False}
    pipeline = JAMPPipeline(kb)

    candidates = [
        Candidate("C1", "a == a", "source_1"),
        Candidate("C2", "0 == 1", "source_1"),
        Candidate("C3", "b == c", "source_1"),
        Candidate(
            "C4",
            "a == a AND 0 == 1",
            "source_1",
            metadata={"is_contradictory": True},
        ),
    ]

    receipts = pipeline.process_candidates(candidates)
    assert [receipt.status for receipt in receipts] == [
        VerificationStatus.CONFIRMED,
        VerificationStatus.REJECTED,
        VerificationStatus.UNKNOWN,
        VerificationStatus.CONFLICT,
    ]
    assert all(receipt.event_id.startswith("EVT_") for receipt in receipts)
    assert all(len(receipt.state_fingerprint) == 64 for receipt in receipts)

    facts = pipeline.registry.by_kind("fact")
    conflicts = pipeline.registry.by_kind("conflict")
    assert len(facts) == 1
    assert facts[0].payload["statement"] == "a == a"
    assert len(conflicts) == 1
    assert conflicts[0].payload["statement"] == "a == a AND 0 == 1"

    assert len(pipeline.dag.nodes) == 5
    evt_ids = list(pipeline.dag.nodes.keys())
    assert evt_ids[0] == pipeline.dag.GENESIS_ID

    events = [node.event_type for node in pipeline.dag.nodes.values()]
    assert events == [
        "GENESIS",
        "FactCommitted",
        "FactRejected",
        "FactUnverified",
        "ConflictDetected",
    ]

    user_evt_ids = evt_ids[1:]
    assert pipeline.dag.nodes[user_evt_ids[1]].parents == [user_evt_ids[0]]
    assert pipeline.dag.nodes[user_evt_ids[3]].parents == [user_evt_ids[2]]

    committed = pipeline.dag.nodes[user_evt_ids[0]]
    assert committed.payload["provenance"]["source_id"] == "source_1"
    assert committed.payload["provenance"]["rule_applied"] == "KB_EXACT_MATCH"
    assert committed.payload["provenance"]["event_id"] == "EVT_0001"
