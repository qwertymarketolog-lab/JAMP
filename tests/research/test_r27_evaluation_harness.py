from __future__ import annotations

import json

from scripts.research.r27_evaluation_harness import (
    CONTRACT_VIOLATION,
    INCONCLUSIVE,
    PARAM_ACCEPTED,
    PARAM_REJECTED,
    PARAM_TRUNCATED,
    PARAM_UNRESOLVED,
    QUALIFIED,
    R28_CANDIDATE,
    aggregate,
    parameter_resolution,
    r28_filter,
)


def response(reason: str = "stop") -> dict:
    return {"choices": [{"finish_reason": reason, "message": {"content": "ok"}}]}


def test_parameter_state_machine() -> None:
    assert parameter_resolution(response("stop"), 200)[0] == PARAM_ACCEPTED
    assert parameter_resolution(response("length"), 200)[0] == PARAM_TRUNCATED
    error = {"error": {"param": "max_tokens", "message": "unsupported"}}
    assert parameter_resolution(error, 400)[0] == PARAM_REJECTED
    assert parameter_resolution({"error": {"message": "bad request"}}, 400)[0] == PARAM_UNRESOLVED
    assert parameter_resolution(response("stop"), 503)[0] == PARAM_UNRESOLVED


def test_no_synthetic_pass_from_truncation() -> None:
    tests = {f"E0{i}": "PASS" for i in range(1, 8)}
    assert aggregate(True, PARAM_TRUNCATED, tests, "PASS") == INCONCLUSIVE
    assert r28_filter(True, True, PARAM_TRUNCATED, tests, "PASS", INCONCLUSIVE) == INCONCLUSIVE


def test_rejected_is_contract_violation() -> None:
    tests = {f"E0{i}": "PASS" for i in range(1, 8)}
    assert aggregate(True, PARAM_REJECTED, tests, "PASS") == CONTRACT_VIOLATION
    assert (
        r28_filter(True, True, PARAM_REJECTED, tests, "PASS", CONTRACT_VIOLATION)
        == CONTRACT_VIOLATION
    )


def test_qualified_requires_parameter_acceptance() -> None:
    tests = {f"E0{i}": "PASS" for i in range(1, 8)}
    assert aggregate(True, PARAM_ACCEPTED, tests, "PASS") == QUALIFIED
    assert r28_filter(True, True, PARAM_ACCEPTED, tests, "PASS", QUALIFIED) == R28_CANDIDATE


def test_e08_inconclusive_blocks_qualification() -> None:
    tests = {f"E0{i}": "PASS" for i in range(1, 8)}
    assert aggregate(True, PARAM_ACCEPTED, tests, "INCONCLUSIVE") == INCONCLUSIVE


def test_r27_source_has_frozen_cardinality() -> None:
    source = json.loads(
        open("artifacts/research/r27_provenance_probe.json", encoding="utf-8").read()
    )
    assert len(source["records"]) == 17
