"""Executable P21.1 acceptance/adversarial gates."""
from __future__ import annotations

import hashlib
import inspect
import json

import pytest

from jamp.research.runtime import RuntimeIntegrityError, RuntimeStage, RuntimeStatus, make_runtime

STAGES = [
    "QUESTION", "PLAN", "EXECUTION", "RESULT",
    "INTERPRETATION", "CONSENSUS", "REVISION",
]


class Artifact:
    def __init__(self, artifact_hash, provenance=(), upstream_hash=None):
        self.result_hash = artifact_hash
        self.artifact_hash = artifact_hash
        self.provenance_chain = tuple(provenance)
        self.upstream_hash = upstream_hash

    def verify(self, *args, **kwargs):
        return True

    def export(self):
        return {
            "artifact_hash": self.artifact_hash,
            "provenance_chain": self.provenance_chain,
            "upstream_hash": self.upstream_hash,
        }


def artifact(name, upstream_hash=None):
    h = hashlib.sha256(name.encode()).hexdigest()
    chain = ((upstream_hash,) if upstream_hash else ()) + (h,)
    return Artifact(h, chain, upstream_hash)


def sample():
    arts = {}
    previous = None
    for stage in STAGES:
        arts[stage] = artifact(stage.lower(), previous)
        previous = arts[stage].artifact_hash
    return make_runtime(context={"research": "demo"}, transitions=STAGES, artifacts=arts)


def chain_artifacts(stages):
    arts = {}
    previous = None
    for stage in stages:
        arts[stage] = artifact(stage.lower(), previous)
        previous = arts[stage].artifact_hash
    return arts


def test_01_schema_validity():
    assert sample().verify()


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
    exported = sample().export()
    assert "timestamp" not in exported and "uuid" not in exported


def test_11_question_integration():
    assert sample().artifact_hashes[RuntimeStage.QUESTION] == artifact("question").artifact_hash


def test_12_plan_integration():
    assert sample().artifact_hashes[RuntimeStage.PLAN] == artifact("plan", artifact("question").artifact_hash).artifact_hash


def test_13_execution_integration():
    assert sample().artifact_hashes[RuntimeStage.EXECUTION] == artifact("execution", artifact("plan", artifact("question").artifact_hash).artifact_hash).artifact_hash


def test_14_result_integration():
    assert RuntimeStage.RESULT in sample().artifact_hashes


def test_15_interpretation_integration():
    assert RuntimeStage.INTERPRETATION in sample().artifact_hashes


def test_16_consensus_integration():
    assert RuntimeStage.CONSENSUS in sample().artifact_hashes


def test_17_revision_integration():
    assert RuntimeStage.REVISION in sample().artifact_hashes


def test_18_upstream_integrity_verification():
    calls = []
    class Checked(Artifact):
        def verify(self, *args, **kwargs):
            calls.append(self.artifact_hash)
            return True
    arts = chain_artifacts(STAGES)
    checked = {s: Checked(v.artifact_hash, v.provenance_chain, v.upstream_hash) for s, v in arts.items()}
    make_runtime(context={}, transitions=STAGES, artifacts=checked)
    assert len(calls) == 7


def test_19_complete_provenance_preservation():
    r = sample()
    assert r.provenance["stages"] == tuple(STAGES)
    assert len(r.provenance["artifact_hashes"]) == 7


def test_20_recursive_provenance_preservation():
    r = sample()
    assert r.provenance["recursive"] is True
    assert len(r.provenance["lineage"]) == 7


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
    arts = {"REVISION": artifact("revision"), "QUESTION": artifact("question", artifact("revision").artifact_hash)}
    r = make_runtime(context={}, transitions=["REVISION", "QUESTION"], artifacts=arts)
    assert r.transitions == (RuntimeStage.REVISION, RuntimeStage.QUESTION)


def test_28_illegal_stage_jump_rejected():
    with pytest.raises(RuntimeIntegrityError):
        make_runtime(context={}, transitions=["QUESTION", "RESULT"], artifacts=chain_artifacts(["QUESTION", "RESULT"]))


def test_29_equivalent_orchestrations_same_hash():
    assert sample().runtime_hash == sample().runtime_hash


def test_30_artifact_substitution_rejected():
    arts = chain_artifacts(STAGES)
    arts["RESULT"] = artifact("substituted")
    with pytest.raises(RuntimeIntegrityError):
        make_runtime(context={"research": "demo"}, transitions=STAGES, artifacts=arts)


def test_31_artifact_mutation_detected():
    r = sample()
    payload = dict(r.export())
    payload["context"] = {"tampered": True}
    assert payload["context"] != r.context
    with pytest.raises(RuntimeIntegrityError):
        type(r).from_export(payload)


def test_32_historical_artifact_immutability():
    arts = chain_artifacts(STAGES)
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
    payload["runtime_hash"] = "b" * 64
    with pytest.raises(RuntimeIntegrityError):
        type(sample()).from_export(payload)


def test_36_upstream_hash_substitution_rejected():
    arts = chain_artifacts(STAGES)
    arts["PLAN"] = artifact("plan-substituted", artifact("question").artifact_hash)
    with pytest.raises(RuntimeIntegrityError):
        make_runtime(context={"research": "demo"}, transitions=STAGES, artifacts=arts)


def test_37_illegal_cycle_rejected():
    with pytest.raises(RuntimeIntegrityError):
        make_runtime(context={}, transitions=["QUESTION", "PLAN", "QUESTION"], artifacts=chain_artifacts(["QUESTION", "PLAN", "QUESTION"]))


def test_38_runtime_metadata_injection_rejected():
    with pytest.raises(RuntimeIntegrityError):
        make_runtime(context={"pid": 1234}, transitions=STAGES, artifacts=chain_artifacts(STAGES))


def test_39_full_chain_reconstruction():
    r = sample()
    assert r.reconstruct_chain() == tuple(STAGES)
    assert r.verify() is True


def test_40_zero_io_network_domain_contamination():
    import jamp.research.runtime as runtime
    source = inspect.getsource(runtime)
    assert "jamp.domain" not in source
    assert "socket" not in source and "requests" not in source
    assert "open(" not in source


def test_gate_count_is_exactly_40():
    tests = [name for name in globals() if name.startswith("test_") and name[5:7].isdigit()]
    assert len(tests) == 40
