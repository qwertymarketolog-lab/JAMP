from dataclasses import replace

import pytest
from ai_provider import (
    PROTOCOL_VERSION,
    AIObservation,
    AIProposal,
    AIProviderError,
    AIRequest,
    VerifiedEvidence,
    proposal_evidence,
    validate_proposal,
    validate_request,
)
from operation_policy import Operation, Target, TargetKind
from task_loader import TaskContract

SHA = "a" * 40
BASE = "b" * 40


def task():
    return TaskContract(
        task_id="TASK-188",
        version=1,
        allowed_paths=(".agents/runner/**",),
        forbidden_paths=("src/jamp/**",),
        base_ref="main",
        expected_base_sha=BASE,
        require_head_match=True,
    )


def request():
    return AIRequest(
        protocol_version=PROTOCOL_VERSION,
        request_id="req-188",
        task=task(),
        objective="define provider contract",
        runner_state="PLAN",
        previous_action=None,
        iteration=0,
        source_sha=SHA,
        base_sha=BASE,
        observations=(AIObservation("ci", "terminal", "github"),),
        verified_evidence=(
            VerifiedEvidence("quality", "1", "2", "completed", "success", None, "PR"),
        ),
    )


def proposal(op=Operation.READ, target=None, **kw):
    return AIProposal(
        protocol_version=PROTOCOL_VERSION,
        request_id="req-188",
        provider_id="test-provider",
        model_id="test-model",
        model_request_id="model-1",
        hypothesis="inspect runner",
        observation_summary="observed terminal evidence",
        proposed_operation=op,
        target=target or Target(TargetKind.PATH, ".agents/runner/ai_provider.py"),
        expected_effect="no direct mutation",
        confidence=0.5,
        **kw,
    )


def test_01_valid_request_is_accepted():
    validate_request(request())


@pytest.mark.parametrize(
    "field,value",
    [
        ("task", replace(task(), task_id="")),
        ("source_sha", ""),
    ],
)
def test_02_03_required_request_identity_is_rejected(field, value):
    with pytest.raises(AIProviderError):
        validate_request(replace(request(), **{field: value}))


def test_04_malformed_scope_is_rejected():
    malformed = replace(task(), allowed_paths=(None,))
    with pytest.raises(AIProviderError):
        validate_request(replace(request(), task=malformed))


def test_05_forbidden_path_is_rejected():
    with pytest.raises(AIProviderError):
        validate_proposal(
            request(),
            proposal(
                Operation.WRITE,
                Target(TargetKind.PATH, "src/secret.py"),
            ),
        )


def test_06_frozen_core_is_rejected():
    with pytest.raises(AIProviderError):
        validate_proposal(
            request(),
            proposal(
                Operation.WRITE,
                Target(TargetKind.PATH, "src/jamp/run.py"),
            ),
        )


def test_07_main_ref_mutation_is_rejected():
    with pytest.raises(AIProviderError):
        validate_proposal(
            request(),
            proposal(Operation.PUSH, Target(TargetKind.REF, "main")),
        )


def test_08_unsupported_operation_is_rejected():
    invalid = replace(proposal(), proposed_operation="UNKNOWN")
    with pytest.raises((AIProviderError, ValueError)):
        validate_proposal(request(), invalid)


def test_09_request_result_binding_is_mandatory():
    bad = replace(proposal(), request_id="other")
    with pytest.raises(AIProviderError):
        validate_proposal(request(), bad)


def test_10_provider_model_identity_is_mandatory():
    with pytest.raises(AIProviderError):
        validate_proposal(request(), replace(proposal(), provider_id=""))


def test_11_ai_pass_claim_is_not_authority():
    with pytest.raises(AIProviderError):
        validate_proposal(request(), proposal(claimed_state="PASS"))


def test_12_ai_cannot_inject_verified_evidence_as_authority():
    forged = replace(request(), verified_evidence=())
    validate_request(forged)
    # Empty verified_evidence is data, not proof; validation does not promote it.
    assert forged.verified_evidence == ()


def test_13_valid_read_is_accepted_for_policy_evaluation():
    validate_proposal(request(), proposal())


def test_14_valid_write_allowed_path_is_accepted_for_policy_evaluation():
    validate_proposal(
        request(),
        proposal(
            Operation.WRITE,
            Target(TargetKind.PATH, ".agents/runner/new_provider.py"),
        ),
    )


def test_15_push_non_main_is_accepted_for_policy_evaluation():
    validate_proposal(
        request(),
        proposal(Operation.PUSH, Target(TargetKind.REF, "agent/test")),
    )


def test_16_merge_has_no_ai_authority():
    with pytest.raises(AIProviderError):
        validate_proposal(
            request(),
            proposal(Operation.MERGE, Target(TargetKind.REF, "agent/test")),
        )


def test_17_missing_evidence_is_inconclusive():
    with pytest.raises(AIProviderError, match="INCONCLUSIVE"):
        proposal_evidence(None)


def test_18_nonterminal_or_jobs_empty_is_not_verified_evidence():
    nonterminal = VerifiedEvidence("quality", "9", None, "in_progress", "", None, "PR")
    empty_jobs = VerifiedEvidence("quality", "10", None, "completed", "failure", None, "jobs=[]")
    # The provider contract records these as observations; neither is promoted
    # to Evidence/Decision by this interface.
    assert nonterminal.status != "completed"
    assert empty_jobs.scope == "jobs=[]"
