"""P15.3 tests for the immutable Search Feedback Channel."""

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from jamp.engine.adapter import emit_search_feedback
from jamp.registry.candidates import Candidate, VerificationResult, VerificationStatus
from jamp.search import FeedbackStatus, SearchBoundary, SearchCandidate, SearchFeedback, SearchProvenance


class RecordingPolicy:
    name = "recording"

    def __init__(self):
        self.feedback = []

    def propose(self, context_statement):
        return []

    def receive_feedback(self, feedback):
        self.feedback.append(feedback)


def make_candidate(node_id="node_1"):
    return SearchCandidate(
        candidate_id="cand_1",
        statement="x",
        source_id="test",
        provenance=SearchProvenance(
            search_node_id=node_id,
            depth=1,
            score=0.5,
            policy_name="recording",
        ),
    )


def test_feedback_is_frozen_and_has_exact_contract():
    feedback = SearchFeedback("node_1", FeedbackStatus.REJECTED, "REJECTED", "RULE_X", 123.0)
    with pytest.raises(FrozenInstanceError):
        feedback.status = FeedbackStatus.ACCEPTED
    assert feedback.__dataclass_params__.frozen is True
    assert feedback.timestamp == 123.0


def test_from_evaluation_maps_verdict_without_state_domain_reference():
    search_candidate = make_candidate("node_7")
    result = VerificationResult(
        candidate=Candidate("cand_1", "x", "test"),
        status=VerificationStatus.REJECTED,
    )
    feedback = SearchFeedback.from_evaluation(search_candidate, result, timestamp=42.0)
    assert feedback == SearchFeedback("node_7", FeedbackStatus.REJECTED, "REJECTED", "VerificationResult", 42.0)


def test_adapter_emits_accepted_feedback_from_confirmed_evaluation():
    search_candidate = make_candidate("node_9")
    result = VerificationResult(
        candidate=Candidate("cand_1", "x", "test"),
        status=VerificationStatus.CONFIRMED,
    )
    feedback = emit_search_feedback(search_candidate, result, timestamp=99.0)
    assert feedback.status is FeedbackStatus.ACCEPTED
    assert feedback.reason is None
    assert feedback.search_node_id == "node_9"
    assert feedback.timestamp == 99.0


def test_boundary_routes_feedback_without_exposing_policy_internals():
    policy = RecordingPolicy()
    boundary = SearchBoundary(policy)
    feedback = SearchFeedback("node_2", FeedbackStatus.UNKNOWN, "UNKNOWN", "eval", 7.0)
    boundary.submit_feedback(feedback)
    assert policy.feedback == [feedback]
    assert policy.feedback[0] is feedback


def test_boundary_accepts_policy_without_feedback_handler():
    class ProposalOnlyPolicy:
        name = "proposal_only"

        def propose(self, context_statement):
            return []

    SearchBoundary(ProposalOnlyPolicy()).submit_feedback(
        SearchFeedback("node", FeedbackStatus.UNKNOWN, None, "eval", 1.0)
    )


def test_state_domain_modules_do_not_import_search_policy_structures():
    source_root = Path(__file__).parents[2] / "src" / "jamp" / "engine"
    forbidden = {"MCTSNode", "SearchPolicy", "PolicyEnsemble"}
    for path in source_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {
            alias.name.rsplit(".", 1)[-1]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        assert not (names & forbidden), f"State Domain import leak in {path.name}"
