from __future__ import annotations

import os

import pytest

from jamp.research import canonical, evidence, hypothesis_formation, hypothesis_scoring as scoring, lineage_graph


_ONE_HASH = canonical.replay_hash("one")
_TWO_HASH = canonical.replay_hash("two")
_THREE_HASH = canonical.replay_hash("three")


def _fixture():
    record_one = evidence.EvidenceRecord(_ONE_HASH, _TWO_HASH, _THREE_HASH, 0)
    record_two = evidence.EvidenceRecord(_TWO_HASH, _THREE_HASH, _THREE_HASH, 1)
    ledger = evidence.build_evidence_ledger((record_one, record_two))
    hypothesis = hypothesis_formation.Hypothesis(
        (record_one.evidence_hash,), _THREE_HASH, "proposition", 0
    )
    graph = lineage_graph.build_lineage_graph((lineage_graph.LineageNode(_THREE_HASH, ()),))
    return ledger, hypothesis, graph


def test_score_is_bounded():
    ledger, hypothesis, graph = _fixture()
    score = scoring.score_hypothesis(hypothesis, ledger, graph)
    assert 0.0 <= score <= 1.0


def test_score_requires_valid_evidence():
    ledger, hypothesis, graph = _fixture()
    assert scoring.score_hypothesis(hypothesis, ledger, graph) > 0.0


def test_empty_ledger_is_zero_evidence_boundary():
    ledger, hypothesis, graph = _fixture()
    empty = evidence.build_evidence_ledger(())
    assert scoring.score_hypothesis(hypothesis, empty, graph) == 0.0


def test_hypothesis_without_evidence_is_rejected():
    ledger, _, graph = _fixture()
    with pytest.raises(ValueError):
        hypothesis = hypothesis_formation.Hypothesis.__new__(hypothesis_formation.Hypothesis)
        object.__setattr__(hypothesis, "hypothesis_hash", _ONE_HASH)
        object.__setattr__(hypothesis, "evidence_refs", ())
        object.__setattr__(hypothesis, "state_hash", _THREE_HASH)
        object.__setattr__(hypothesis, "proposition", "no evidence")
        object.__setattr__(hypothesis, "sequence", 0)
        scoring.score_hypothesis(hypothesis, ledger, graph)


def test_duplicate_evidence_references_cannot_inflate_support():
    ledger, hypothesis, graph = _fixture()
    duplicate = hypothesis_formation.Hypothesis.__new__(hypothesis_formation.Hypothesis)
    object.__setattr__(duplicate, "hypothesis_hash", hypothesis.hypothesis_hash)
    object.__setattr__(duplicate, "evidence_refs", (ledger.records[0].evidence_hash,) * 2)
    object.__setattr__(duplicate, "state_hash", hypothesis.state_hash)
    object.__setattr__(duplicate, "proposition", hypothesis.proposition)
    object.__setattr__(duplicate, "sequence", hypothesis.sequence)
    with pytest.raises(ValueError):
        scoring.score_hypothesis(duplicate, ledger, graph)


def test_tampered_ledger_is_rejected():
    ledger, hypothesis, graph = _fixture()
    tampered = evidence.EvidenceRecord(_ONE_HASH, _TWO_HASH, _ONE_HASH, 0)
    bad_ledger = evidence.build_evidence_ledger((tampered, ledger.records[1]))
    with pytest.raises(ValueError):
        scoring.score_hypothesis(hypothesis, bad_ledger, graph)


def test_tampered_lineage_is_rejected():
    ledger, hypothesis, _ = _fixture()
    bad_node = lineage_graph.LineageNode(_THREE_HASH, (_ONE_HASH,))
    bad_graph = lineage_graph.LineageGraph((bad_node,))
    with pytest.raises(ValueError):
        scoring.score_hypothesis(hypothesis, ledger, bad_graph)


def test_invalid_provenance_cannot_produce_positive_support():
    ledger, hypothesis, graph = _fixture()
    bad = hypothesis_formation.Hypothesis.__new__(hypothesis_formation.Hypothesis)
    object.__setattr__(bad, "hypothesis_hash", _ONE_HASH)
    object.__setattr__(bad, "evidence_refs", hypothesis.evidence_refs)
    object.__setattr__(bad, "state_hash", _ONE_HASH)
    object.__setattr__(bad, "proposition", hypothesis.proposition)
    object.__setattr__(bad, "sequence", 0)
    with pytest.raises(ValueError):
        scoring.score_hypothesis(bad, ledger, graph)


def test_score_is_deterministic():
    ledger, hypothesis, graph = _fixture()
    assert scoring.score_hypothesis(hypothesis, ledger, graph) == scoring.score_hypothesis(
        hypothesis, ledger, graph
    )


def test_score_is_environment_invariant(monkeypatch):
    ledger, hypothesis, graph = _fixture()
    baseline = scoring.score_hypothesis(hypothesis, ledger, graph)
    monkeypatch.setenv("JAMP_SCORING_NOISE", "999999")
    assert scoring.score_hypothesis(hypothesis, ledger, graph) == baseline


def test_score_is_process_environment_invariant():
    ledger, hypothesis, graph = _fixture()
    baseline = scoring.score_hypothesis(hypothesis, ledger, graph)
    original = os.environ.get("JAMP_SCORING_NOISE")
    try:
        os.environ["JAMP_SCORING_NOISE"] = "123456"
        assert scoring.score_hypothesis(hypothesis, ledger, graph) == baseline
    finally:
        if original is None:
            os.environ.pop("JAMP_SCORING_NOISE", None)
        else:
            os.environ["JAMP_SCORING_NOISE"] = original


def test_serialization_equivalent_inputs_have_equal_score():
    ledger, hypothesis, graph = _fixture()
    rebuilt = hypothesis_formation.Hypothesis(
        tuple(hypothesis.evidence_refs),
        str(hypothesis.state_hash),
        str(hypothesis.proposition),
        hypothesis.sequence,
    )
    assert scoring.score_hypothesis(hypothesis, ledger, graph) == scoring.score_hypothesis(
        rebuilt, ledger, graph
    )


def test_independent_evidence_extension_is_monotone():
    ledger, hypothesis, graph = _fixture()
    baseline = scoring.score_hypothesis(hypothesis, ledger, graph)
    extended = hypothesis_formation.Hypothesis(
        (ledger.records[0].evidence_hash, ledger.records[1].evidence_hash),
        hypothesis.state_hash,
        hypothesis.proposition,
        hypothesis.sequence,
    )
    extended_score = scoring.score_hypothesis(extended, ledger, graph)
    assert ledger.records[0].source_hash != ledger.records[1].source_hash
    assert extended_score >= baseline


def test_score_is_non_interfering_with_competing_sibling_context():
    ledger, hypothesis, graph = _fixture()
    baseline_ledger = evidence.build_evidence_ledger((ledger.records[0],))
    baseline = scoring.score_hypothesis(hypothesis, baseline_ledger, graph)

    sibling = hypothesis_formation.Hypothesis(
        (ledger.records[1].evidence_hash,), _THREE_HASH, "competing sibling", 0
    )
    concurrent = scoring.score_hypothesis(sibling, ledger, graph)

    assert sibling.hypothesis_hash != hypothesis.hypothesis_hash
    assert concurrent != baseline
    assert scoring.score_hypothesis(hypothesis, ledger, graph) == baseline


def test_score_does_not_depend_on_object_identity():
    ledger, hypothesis, graph = _fixture()
    other_ledger, other_hypothesis, other_graph = _fixture()
    assert scoring.score_hypothesis(hypothesis, ledger, graph) == scoring.score_hypothesis(
        other_hypothesis, other_ledger, other_graph
    )


def test_score_is_read_only():
    ledger, hypothesis, graph = _fixture()
    before = (ledger, hypothesis, graph)
    scoring.score_hypothesis(hypothesis, ledger, graph)
    assert (ledger, hypothesis, graph) == before


def test_public_api_is_explicit():
    assert set(scoring.__all__) == {"score_hypothesis"}
