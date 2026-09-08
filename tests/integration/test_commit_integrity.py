"""Tests for the authoritative Commit Manager contract."""

import pytest

from jamp.engine.commit import CommitManager, UnauthorizedCommitError
from jamp.events.dag import EventDAG
from jamp.registry.candidates import Candidate, VerificationResult, VerificationStatus
from jamp.registry.registry import Registry, RegistryRecord, UnauthorizedRegistryMutation


def test_commit_without_provenance_fails():
    registry = Registry()
    dag = EventDAG()
    manager = CommitManager(registry, dag)

    invalid_result = VerificationResult(
        candidate=Candidate("C_BAD", "x == 1", "source_ai"),
        status=VerificationStatus.CONFIRMED,
        provenance=None,
    )

    with pytest.raises(UnauthorizedCommitError):
        manager.commit(invalid_result)

    assert len(registry.facts) == 0
    assert set(dag.nodes) == {EventDAG.GENESIS_ID}


def test_direct_registry_mutation_is_blocked():
    registry = Registry()

    with pytest.raises(UnauthorizedRegistryMutation):
        registry.add(
            RegistryRecord(
                record_id="FACT_BYPASS",
                kind="fact",
                payload={"statement": "bypass"},
            )
        )

    assert registry.all() == ()


def test_commit_receipt_matches_dag_event():
    registry = Registry()
    dag = EventDAG()
    manager = CommitManager(registry, dag)

    from jamp.registry.candidates import Provenance

    result = VerificationResult(
        candidate=Candidate("C_OK", "x == 1", "source_ai"),
        status=VerificationStatus.CONFIRMED,
        provenance=Provenance(
            source_id="source_ai",
            rule_applied="KB_EXACT_MATCH",
            evidence_id="EVID_TEST",
            event_id="EVT_0001",
            fingerprint="a" * 64,
        ),
    )

    receipt = manager.commit(result)
    event = dag.nodes[receipt.event_id]

    assert receipt.event_id == event.event_id
    assert receipt.state_fingerprint == event.hash
    assert receipt.status is VerificationStatus.CONFIRMED
    assert registry.facts == frozenset({"x == 1"})
