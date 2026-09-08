"""Unit tests for the P15.1 Search Domain policy ensemble."""

import pytest

from jamp.search.boundary import SearchBoundary
from jamp.search.candidate import SearchCandidate, SearchProvenance
from jamp.search.ensemble import PolicyEnsemble


class StubPolicy:
    def __init__(self, name: str, statements: tuple[str, ...]) -> None:
        self._name = name
        self._statements = statements

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
                    score=0.5,
                    policy_name=self._name,
                ),
            )
            for index, statement in enumerate(self._statements)
        ]


def test_ensemble_runs_policies_in_declaration_order_and_preserves_candidates():
    first = StubPolicy("first", ("A", "B"))
    second = StubPolicy("second", ("C",))
    ensemble = PolicyEnsemble((first, second))

    result = ensemble.search("context")

    assert result.policy_name == "ensemble[first,second]"
    assert tuple(candidate.statement for candidate in result.candidates) == ("A", "B", "C")
    assert tuple(candidate.provenance.policy_name for candidate in result.candidates) == (
        "first",
        "first",
        "second",
    )


def test_ensemble_satisfies_search_boundary_contract():
    ensemble = PolicyEnsemble(
        (
            StubPolicy("mcts", ("A",)),
            StubPolicy("heuristic", ("B",)),
        )
    )

    result = SearchBoundary(ensemble).expand_and_propose("context")

    assert result.policy_name == "ensemble[mcts,heuristic]"
    assert isinstance(result.candidates, tuple)
    assert [candidate.statement for candidate in result.candidates] == ["A", "B"]


def test_ensemble_is_nonempty_and_rejects_empty_configuration():
    with pytest.raises(ValueError, match="at least one"):
        PolicyEnsemble(())


def test_ensemble_exposes_immutable_policy_tuple():
    ensemble = PolicyEnsemble((StubPolicy("a", ("A",)),))

    assert isinstance(ensemble.policies, tuple)
    with pytest.raises(AttributeError):
        ensemble.policies = ()  # type: ignore[misc]
