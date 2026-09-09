"""P22.9 deterministic hypothesis scoring contract.

Contract-first diagnostic: this module intentionally targets an absent
implementation. Scoring is structural support derived from a validated
hypothesis, evidence ledger, and lineage graph.
"""

import os

import pytest

from jamp.research import evidence
from jamp.research import hypothesis_formation
from jamp.research import hypothesis_scoring as scoring
from jamp.research import lineage_graph

_ZERO_HASH = "0" * 64
_ONE_HASH = "1" * 64
_TWO_HASH = "2" * 64
_THREE_HASH = "3" * 64


def _fixture():
    records = (
        evidence.EvidenceRecord(_ONE_HASH, _TWO_HASH, _THREE_HASH, 0),
        evidence.EvidenceRecord(_TWO_HASH, _THREE_HASH, _THREE_HASH, 1),
    )
    ledger = evidence.build_evidence_ledger(records)
    hypothesis = hypothesis_formation.Hypothesis(
        (records[0].evidence_hash,), _THREE_HASH, "test proposition", 0
    )
    root = lineage_graph.LineageNode(_ZERO_HASH, ())
    state = lineage_graph.LineageNode(_THREE_HASH, (_ZERO_HASH,))
    graph = lineage_graph.build_lineage_graph((root, state))
    return ledger, hypothesis, graph


def test_score_is_bounded():
    ledger, hypothesis, graph = _fixture()
    assert 0.0 <= scoring.score_hypothesis(hypothesis, ledger, graph) <= 1.0


def test_score_requires_valid_evidence_backing():
    ledger, _, graph = _fixture()
    missing = hypothesis_formation.Hypothesis(
        ("4" * 64,), _THREE_HASH, "test proposition", 0
    )
    with pytest.raises(ValueError, match="evidence"):
        scoring.score_hypothesis(missing, ledger, graph)


def test_empty_ledger_is_zero_evidence_boundary():
    ledger, hypothesis, graph = _fixture()
    empty = evidence.build_evidence_ledger(())
    assert empty.records == ()
    assert scoring.score_hypothesis(hypothesis, empty, graph) == 0.0


def test_duplicate_evidence_references_cannot_inflate_support():
    ledger, hypothesis, graph = _fixture()
    duplicate = hypothesis_formation.Hypothesis.__new__(hypothesis_formation.Hypothesis)
    object.__setattr__(duplicate, "evidence_refs", (hypothesis.evidence_refs[0],) * 2)
    object.__setattr__(duplicate, "state_hash", hypothesis.state_hash)
    object.__setattr__(duplicate, "proposition", hypothesis.proposition)
    object.__setattr__(duplicate, "sequence", hypothesis.sequence)
    object.__setattr__(duplicate, "hypothesis_hash", hypothesis.hypothesis_hash)
    with pytest.raises(ValueError, match="duplicate"):
        scoring.score_hypothesis(duplicate, ledger, graph)


def test_tampered_ledger_is_rejected():
    ledger, hypothesis, graph = _fixture()
    object.__setattr__(ledger.records[0], "source_hash", _ZERO_HASH)
    with pytest.raises(ValueError):
        scoring.score_hypothesis(hypothesis, ledger, graph)


def test_tampered_lineage_is_rejected():
    ledger, hypothesis, graph = _fixture()
    object.__setattr__(graph, "graph_hash", _ONE_HASH)
    with pytest.raises(ValueError):
        scoring.score_hypothesis(hypothesis, ledger, graph)


def test_invalid_provenance_cannot_produce_positive_support():
    ledger, hypothesis, graph = _fixture()
    object.__setattr__(hypothesis, "state_hash", _ZERO_HASH)
    with pytest.raises(ValueError):
        scoring.score_hypothesis(hypothesis, ledger, graph)


def test_scoring_is_deterministic():
    ledger, hypothesis, graph = _fixture()
    first = scoring.score_hypothesis(hypothesis, ledger, graph)
    second = scoring.score_hypothesis(hypothesis, ledger, graph)
    assert first == second


def test_scoring_is_environment_invariant(monkeypatch):
    ledger, hypothesis, graph = _fixture()
    monkeypatch.setenv("PYTHONHASHSEED", "random")
    monkeypatch.setenv("JAMP_P22_9_FORBIDDEN", "one")
    first = scoring.score_hypothesis(hypothesis, ledger, graph)
    monkeypatch.setenv("JAMP_P22_9_FORBIDDEN", "two")
    assert scoring.score_hypothesis(hypothesis, ledger, graph) == first


def test_scoring_does_not_depend_on_process_environment(monkeypatch):
    ledger, hypothesis, graph = _fixture()
    monkeypatch.setattr(os, "environ", {"JAMP_P22_9_FORBIDDEN": "1"})
    first = scoring.score_hypothesis(hypothesis, ledger, graph)
    monkeypatch.setattr(os, "environ", {"JAMP_P22_9_FORBIDDEN": "2"})
    assert scoring.score_hypothesis(hypothesis, ledger, graph) == first


def test_serialization_equivalent_inputs_score_identically():
    ledger, hypothesis, graph = _fixture()
    ledger_copy = evidence.EvidenceLedger(
        tuple(
            evidence.EvidenceRecord(r.source_hash, r.payload_hash, r.state_hash, r.sequence)
            for r in ledger.records
        ),
        ledger.ledger_hash,
    )
    hypothesis_copy = hypothesis_formation.Hypothesis(
        tuple(hypothesis.export()["evidence_refs"]),
        hypothesis.state_hash,
        hypothesis.proposition,
        hypothesis.sequence,
    )
    graph_copy = lineage_graph.build_lineage_graph(
        tuple(lineage_graph.LineageNode(n.node_hash, n.parents) for n in graph.nodes)
    )
    assert scoring.score_hypothesis(hypothesis, ledger, graph) == scoring.score_hypothesis(
        hypothesis_copy, ledger_copy, graph_copy
    )


def test_independent_evidence_extension_is_monotone():
    ledger, hypothesis, graph = _fixture()
    baseline = scoring.score_hypothesis(hypothesis, ledger, graph)
    extended = hypothesis_formation.Hypothesis(
        tuple(record.evidence_hash for record in ledger.records),
        _THREE_HASH,
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
        (ledger.records[1].evidence_hash,), _THREE_HASH, "competing sibling", 1
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
    before = (ledger.export(), hypothesis.export(), graph.export())
    scoring.score_hypothesis(hypothesis, ledger, graph)
    assert (ledger.export(), hypothesis.export(), graph.export()) == before


def test_public_boundary_is_explicit():
    assert set(scoring.__all__) == {"score_hypothesis"}
