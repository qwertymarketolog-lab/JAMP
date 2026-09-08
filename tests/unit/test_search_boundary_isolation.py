"""Architectural tests for the P13 Search Boundary."""

import ast
from pathlib import Path

import pytest

from jamp.search.boundary import SearchBoundary
from jamp.search.candidate import SearchCandidate, SearchProvenance, SearchResult


FORBIDDEN_MODULE_PARTS = {"registry", "events", "commit", "transaction"}


def test_search_domain_has_no_state_domain_imports():
    """Search Domain must not import Registry, EventDAG, or CommitManager."""

    search_dir = Path("src/jamp/search")
    for py_file in search_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = (alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = (node.module,)
            else:
                continue
            for module in modules:
                assert not any(
                    part in module.split(".") for part in FORBIDDEN_MODULE_PARTS
                ), f"Forbidden state-domain import '{module}' in {py_file}"


def test_search_result_is_immutable_and_uses_tuple():
    provenance = SearchProvenance("node-1", 2, 0.75, "test-policy")
    candidate = SearchCandidate("c-1", "x = 2", "source-1", provenance)
    result = SearchResult((candidate,), "x", "test-policy")

    assert isinstance(result.candidates, tuple)
    with pytest.raises((AttributeError, TypeError)):
        result.context_statement = "changed"


def test_search_boundary_wraps_policy_output():
    class FakePolicy:
        name = "fake"

        def propose(self, context_statement: str):
            return [
                SearchCandidate(
                    "c-1",
                    f"{context_statement} -> candidate",
                    "source-1",
                    SearchProvenance("node-1", 1, 0.5, self.name),
                )
            ]

    result = SearchBoundary(FakePolicy()).expand_and_propose("context")

    assert result.policy_name == "fake"
    assert result.context_statement == "context"
    assert len(result.candidates) == 1
    assert result.candidates[0].candidate_id == "c-1"
