"""Unit tests for P15.2 candidate merge and deduplication."""

from dataclasses import FrozenInstanceError
import hashlib

from jamp.search.candidate import CompositeSearchProvenance, SearchCandidate, SearchProvenance
from jamp.search.dedup import CandidateDeduplicator
from jamp.search.ensemble import PolicyEnsemble


class StubPolicy:
    def __init__(self, name: str, statements: tuple[str, ...], score: float) -> None:
        self._name = name
        self._statements = statements
        self._score = score

    @property
    def name(self) -> str:
        return self._name

    def propose(self, context_statement: str) -> list[SearchCandidate]:
        return [
            SearchCandidate(
                candidate_id=f"{self._name}_{index}",
                statement=statement,
                source_id=self._name,
                provenance=SearchProvenance(
                    search_node_id=f"{self._name}_node_{index}",
                    depth=1,
                    score=self._score,
                    policy_name=self._name,
                ),
            )
            for index, statement in enumerate(self._statements)
        ]


def test_canonicalization_and_sha256_identity_are_deterministic():
    statement = "  P = Q  "
    canonical = "p = q"
    assert CandidateDeduplicator.canonicalize_statement(statement) == canonical
    assert CandidateDeduplicator.identity_key(statement) == hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def test_duplicate_hypotheses_merge_all_provenance_and_select_highest_score():
    candidates = [
        StubPolicy("mcts", ("  P = Q",), 0.4).propose("context")[0],
        StubPolicy("heuristic", ("p = q  ",), 0.9).propose("context")[0],
        StubPolicy("bfs", ("P = Q",), 0.7).propose("context")[0],
    ]

    result = CandidateDeduplicator.deduplicate(candidates)

    assert len(result) == 1
    merged = result[0]
    assert isinstance(merged.provenance, CompositeSearchProvenance)
    assert merged.provenance.primary_provenance.policy_name == "heuristic"
    assert merged.provenance.primary_provenance.search_node_id == "heuristic_node_0"
    assert merged.provenance.sources == ("mcts", "heuristic", "bfs")
    assert tuple(p.search_node_id for p in merged.provenance.contributing_provenances) == (
        "mcts_node_0",
        "bfs_node_0",
    )
    assert merged.provenance.aggregated_score == 0.9


def test_unique_candidates_keep_original_provenance_and_order():
    first = StubPolicy("a", ("A",), 0.2).propose("context")[0]
    second = StubPolicy("b", ("B",), 0.8).propose("context")[0]
    result = CandidateDeduplicator.deduplicate((first, second))
    assert result == [first, second]
    assert isinstance(result[0].provenance, SearchProvenance)


def test_policy_ensemble_applies_deduplication_before_search_result():
    ensemble = PolicyEnsemble(
        (
            StubPolicy("mcts", ("A", "B"), 0.4),
            StubPolicy("heuristic", (" a ", "C"), 0.9),
        )
    )
    result = ensemble.search("context")
    assert tuple(candidate.statement for candidate in result.candidates) == (" a ", "B", "C")
    assert isinstance(result.candidates[0].provenance, CompositeSearchProvenance)


def test_composite_provenance_is_immutable():
    candidate = StubPolicy("a", ("A",), 0.5).propose("context")[0]
    merged = CandidateDeduplicator.deduplicate((candidate, StubPolicy("b", ("A",), 0.6).propose("context")[0]))[0]
    assert isinstance(merged.provenance, CompositeSearchProvenance)
    try:
        merged.provenance.aggregated_score = 1.0  # type: ignore[misc]
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("CompositeSearchProvenance must be immutable")
