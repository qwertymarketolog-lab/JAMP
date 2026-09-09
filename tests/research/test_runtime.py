"""Executable P21.1 acceptance/adversarial gates."""
from __future__ import annotations

import hashlib
import json

import pytest

from jamp.research.runtime import (
    RuntimeErrorBase,
    RuntimeIntegrityError,
    RuntimeStage,
    RuntimeStatus,
    compute_runtime_hash,
    make_runtime,
)

HASH = "a" * 64
HASH2 = "b" * 64
HASH3 = "c" * 64
STAGES = [
    "QUESTION", "PLAN", "EXECUTION", "RESULT",
    "INTERPRETATION", "CONSENSUS", "REVISION",
]


class Artifact:
    def __init__(self, artifact_hash=HASH, provenance=()):
        self.result_hash = artifact_hash
        self.artifact_hash = artifact_hash
        self.provenance_chain = tuple(provenance)

    def verify(self, *args, **kwargs):
        return True

    def export(self):
        return {"artifact_hash": self.artifact_hash, "provenance_chain": self.provenance_chain}


def artifact(name):
    return Artifact(hashlib.sha256(name.encode()).hexdigest(), (name,))


def sample():
    artifacts = {stage: artifact(stage.lower()) for stage in STAGES}
    return make_runtime(
        context={"research": "demo"},
        transitions=STAGES,
        artifacts=artifacts,
    )


def test_01_schema_validity():
    r = sample()
    assert r.verify()


def test_02_immutable_runtime_record():
    r = sample()
    with pytest.raises((AttributeError, TypeError)):
        r.status = RuntimeStatus.VERIFIED


def test_03_valid_runtime_hash():
    r = sample()
    assert len(r.runtime_hash) == 64 and int(r.runtime_hash, 16) >= 0


def test_04_deterministic_runtime_identity():
    assert sample().runtime_hash == sample().runtime_hash


def test_05_self_verification():
    assert sample().verify() is True


def test_06_explicit_context():
    assert sample().context["research"] == "demo"


def test_07_explicit_stage_transitions():
    assert sample().transitions == tuple(RuntimeStage(x) for x in STAGES)


def test_08_valid_runtime_state():
    assert sample().status is RuntimeStatus.VERIFIED


def test_09_deterministic_orchestration():
    assert sample().export() == sample().export()


def test_10_runtime_independent_identity():
    assert "timestamp" not in sample().export()
    assert "uuid" not in sample().export()


def test_11_question_integration():
    r = sample()
    assert r.artifact_hashes[RuntimeStage.QUESTION] == artifact("question").artifact_hash


def test_12_plan_integration():
    assert sample().artifact_hashes[RuntimeStage.PLAN] == artifact("plan").artifact_hash


def test_13_execution_integration():
    assert sample().artifact_hashes[RuntimeStage.EXECUTION] == artifact("execution").artifact_hash


def test_14_result_integration():
    assert sample().artifact_hashes[RuntimeStage.RESULT] == artifact("result").artifact_hash


def test_15_interpretation_integration():
    assert sample().artifact_hashes[RuntimeStage.INTERPRETATION] == artifact("interpretation").artifact_hash


def test_16_consensus_integration():
    assert sample().artifact_hashes[RuntimeStage.CONSENSUS] == artifact("consensus").artifact_hash


def test_17_revision_integration():
    assert sample().artifact_hashes[RuntimeStage.REVISION] == artifact("revision").artifact_hash


def test_18_upstream_integrity_verification():
    calls = []
    class Checked(Artifact):
        def verify(self, *args, **kwargs):
            calls.append(self.artifact_hash)
            return True
    arts = {s: Checked(hashlib.sha256(s.lower().encode()).hexdigest()) for s in STAGES}
    make_runtime(context={}, transitions=STAGES, artifacts=arts)
    assert len(calls) == 7


def test_19_complete_provenance_preservation():
    r = sample()
    assert r.provenance["stages"] == tuple(STAGES)
    assert len(r.provenance["artifact_hashes"]) == 7


def test_20_recursive_provenance_preservation():
    arts = {s: Artifact(hashlib.sha256(s.lower().encode()).hexdigest(), ("parent", s)) for s in STAGES}
    r = make_runtime(context={}, transitions=STAGES, artifacts=arts)
    assert r.provenance["recursive"] is True


def test_21_question_to_plan():
    assert sample().transitions[:2] == (RuntimeStage.QUESTION, RuntimeStage.PLAN)


def test_22_plan_to_execution():
    assert sample().transitions[1:3] == (RuntimeStage.PLAN, RuntimeStage.EXECUTION)


def test_23_execution_to_result():
    assert sample().transitions[2:4] == (RuntimeStage.EXECUTION, RuntimeStage.RESULT)


def test_24_result_to_interpretation():
    assert sample().transitions[3:5] == (RuntimeStage.RESULT, RuntimeStage.INTERPRETATION)


def test_25_interpretation_to_consensus():
    assert sample().transitions[4:6] == (RuntimeStage.INTERPRETATION, RuntimeStage.CONSENSUS)


def test_26_consensus_to_revision():
    assert sample().transitions[5:7] == (RuntimeStage.CONSENSUS, RuntimeStage.REVISION)


def test_27_revision_to_question():
    r = make_runtime(context={}, transitions=["REVISION", "QUESTION"], artifacts={"REVISION": artifact("r"), "QUESTION": artifact("q")})
    assert r.transitions == (RuntimeStage.REVISION, RuntimeStage.QUESTION)


def test_28_illegal_stage_jump_rejected():
    with pytest.raises(RuntimeIntegrityError):
        make_runtime(context={}, transitions=["QUESTION", "RESULT"], artifacts={"QUESTION": artifact("q"), "RESULT": artifact("r")})


def test_29_equivalent_orchestrations_same_hash():
    a = sample()
    arts = {s: artifact(s.lower()) for s in reversed(STAGES)}
    b = make_runtime(context={"research": "demo"}, transitions=list(reversed(STAGES))[::-1], artifacts=arts)
    assert a.runtime_hash == b.runtime_hash


def test_30_artifact_substitution_rejected():
    arts = {s: artifact(s.lower()) for s in STAGES}
    arts["RESULT"] = artifact("substituted")
    with pytest.raises(RuntimeIntegrityError):
        make_runtime(context={}, transitions=STAGES, artifacts=arts)


def test_31_artifact_mutation_detected():
    r = sample()
    payload = dict(r.export())
    payload["context"] = {"tampered": True}
    assert payload["context"] != r.context
    with pytest.raises(RuntimeIntegrityError):
        type(r).from_export(payload)


def test_32_historical_artifact_immutability():
    arts = {s: artifact(s.lower()) for s in STAGES}
    r = make_runtime(context={}, transitions=STAGES, artifacts=arts)
    before = r.artifact_hashes
    arts["RESULT"] = artifact("changed")
    assert r.artifact_hashes == before


def test_33_deterministic_provenance_projection():
    assert sample().provenance == sample().provenance


def test_34_cross_runtime_byte_identity():
    a = sample().export()
    b = sample().export()
    assert json.dumps(a, sort_keys=True, separators=(",", ":"), default=list).encode() == json.dumps(b, sort_keys=True, separators=(",", ":"), default=list).encode()


def test_35_runtime_payload_tampering_detected():
    payload = dict(sample().export())
    payload["runtime_hash"] = HASH2
    with pytest.raises(RuntimeIntegrityError):
        type(sample()).from_export(payload)


def test_36_upstream_hash_substitution_rejected():
    arts = {s: artifact(s.lower()) for s in STAGES}
    arts["PLAN"] = Artifact(HASH2)
    with pytest.raises(RuntimeIntegrityError):
        make_runtime(context={"research": "demo"}, transitions=STAGES, artifacts=arts)


def test_37_illegal_cycle_rejected():
    with pytest.raises(RuntimeIntegrityError):
        make_runtime(context={}, transitions=["QUESTION", "PLAN", "QUESTION"], artifacts={"QUESTION": artifact("q"), "PLAN": artifact("p")})


def test_38_runtime_metadata_injection_rejected():
    with pytest.raises(RuntimeIntegrityError):
        make_runtime(context={"pid": 1234}, transitions=STAGES, artifacts={s: artifact(s.lower()) for s in STAGES})


def test_39_full_chain_reconstruction():
    r = sample()
    assert r.reconstruct_chain() == tuple(STAGES)
    assert r.verify() is True


def test_40_zero_io_network_domain_contamination():
    import inspect
    import jamp.research.runtime as runtime
    source = inspect.getsource(runtime)
    assert "jamp.domain" not in source
    assert "socket" not in source and "requests" not in source
    assert "open(" not in source


def test_gate_count_is_exactly_40():
    tests = [name for name in globals() if name.startswith("test_") and name[5:7].isdigit()]
    assert len(tests) == 40
