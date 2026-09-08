"""P20.3 acceptance and adversarial contract: Evidence Derivation & Meta-Analysis."""

from dataclasses import FrozenInstanceError

import pytest

from jamp.research.canonical import replay_hash
from jamp.research.derivation import (
    DerivationIntegrityError,
    derive_evidence,
    compute_derived_evidence_hash,
)
from jamp.research.registry import ArtifactRegistry
from jamp.research.replay import ReplayTrace, compute_trace_hash
from jamp.research.result import compute_result_hash, ResearchResult


def _result(seed: str) -> ResearchResult:
    initial = replay_hash({"seed": seed, "state": "initial"})
    event = replay_hash({"seed": seed, "event": "observation"})
    resulting = replay_hash({"seed": seed, "state": "result"})
    trace_hash = compute_trace_hash(initial, (event,), resulting)
    result_type = "measurement"
    payload = {"value": len(seed), "label": seed}
    provenance = {"source": "test", "operation": "fixture", "version": "1"}
    result_hash = compute_result_hash(trace_hash, result_type, payload, provenance)
    return ResearchResult(trace_hash, result_type, payload, provenance, result_hash)


def _registry(*seeds: str):
    registry = ArtifactRegistry()
    for seed in seeds:
        result = _result(seed)
        initial = replay_hash({"seed": seed, "state": "initial"})
        event = replay_hash({"seed": seed, "event": "observation"})
        resulting = replay_hash({"seed": seed, "state": "result"})
        trace_hash = compute_trace_hash(initial, (event,), resulting)
        trace = ReplayTrace(initial, (event,), resulting, trace_hash)
        registry.register(result, trace)
    return registry


def test_01_schema_validity():
    registry = _registry("a")
    artifact = derive_evidence(registry, [next(iter(registry.snapshot()))], "OBSERVATION", "1", {}, {"x": 1})
    assert artifact.analysis_type == "OBSERVATION"
    assert artifact.algorithm_version == "1"


def test_02_structural_immutability():
    registry = _registry("a")
    artifact = derive_evidence(registry, list(registry.snapshot()), "OBSERVATION", "1", {}, {"x": 1})
    with pytest.raises(FrozenInstanceError):
        artifact.analysis_type = "COMPARISON"
    with pytest.raises(TypeError):
        artifact.parameters["x"] = 2


def test_03_valid_derived_hash():
    registry = _registry("a")
    h = next(iter(registry.snapshot()))
    artifact = derive_evidence(registry, [h], "OBSERVATION", "1", {"a": 1}, {"x": 1})
    assert artifact.derived_evidence_hash == compute_derived_evidence_hash(
        artifact.source_hashes, artifact.analysis_type, artifact.algorithm_version,
        artifact.parameters, artifact.result
    )


def test_04_deterministic_hash_computation():
    args = (["a" * 64], "OBSERVATION", "1", {"z": 2, "a": 1}, {"x": [1, 2]})
    assert compute_derived_evidence_hash(*args) == compute_derived_evidence_hash(*args)


def test_05_self_verification():
    registry = _registry("a")
    h = next(iter(registry.snapshot()))
    artifact = derive_evidence(registry, [h], "OBSERVATION", "1", {}, {"x": 1})
    assert artifact.verify(registry)


def test_06_empty_input_semantics():
    registry = _registry()
    artifact = derive_evidence(registry, [], "OBSERVATION", "1", {}, {"x": 0})
    assert artifact.source_hashes == ()
    with pytest.raises(DerivationIntegrityError):
        derive_evidence(registry, [], "INFERENCE", "1", {}, {"x": 0})


def test_07_registry_backed_source_requirement():
    registry = _registry("a")
    with pytest.raises(DerivationIntegrityError):
        derive_evidence(registry, ["0" * 64], "OBSERVATION", "1", {}, {"x": 1})


def test_08_unknown_source_rejected():
    registry = _registry("a")
    with pytest.raises(DerivationIntegrityError):
        derive_evidence(registry, ["f" * 64], "OBSERVATION", "1", {}, {"x": 1})


def test_09_source_integrity_verified():
    registry = _registry("a")
    h = next(iter(registry.snapshot()))
    object.__setattr__(registry._artifacts[h].result, "result_hash", "0" * 64)
    with pytest.raises(DerivationIntegrityError):
        derive_evidence(registry, [h], "OBSERVATION", "1", {}, {"x": 1})


def test_10_complete_provenance_preserved():
    registry = _registry("a")
    h = next(iter(registry.snapshot()))
    artifact = derive_evidence(registry, [h], "OBSERVATION", "1", {}, {"x": 1})
    assert artifact.provenance[h]["trace_hash"] == registry.get(h).trace_hash
    assert artifact.provenance[h]["event_ids"]
    assert artifact.provenance[h]["state_anchors"]


def test_11_result_hash_preserved():
    registry = _registry("a")
    h = next(iter(registry.snapshot()))
    artifact = derive_evidence(registry, [h], "OBSERVATION", "1", {}, {"x": 1})
    assert h in artifact.source_hashes


def test_12_trace_hash_preserved():
    registry = _registry("a")
    h = next(iter(registry.snapshot()))
    artifact = derive_evidence(registry, [h], "OBSERVATION", "1", {}, {"x": 1})
    assert artifact.provenance[h]["trace_hash"] == registry.get(h).trace_hash


def test_13_event_identity_preserved():
    registry = _registry("a")
    h = next(iter(registry.snapshot()))
    artifact = derive_evidence(registry, [h], "OBSERVATION", "1", {}, {"x": 1})
    assert tuple(artifact.provenance[h]["event_ids"]) == registry.index[h]["ordered_event_ids"]


def test_14_state_anchors_preserved():
    registry = _registry("a")
    h = next(iter(registry.snapshot()))
    artifact = derive_evidence(registry, [h], "OBSERVATION", "1", {}, {"x": 1})
    assert tuple(artifact.provenance[h]["state_anchors"]) == (registry.index[h]["initial_state_hash"], registry.index[h]["resulting_state_hash"])


def test_15_registry_tampering_detected():
    registry = _registry("a")
    h = next(iter(registry.snapshot()))
    registry._index[h] = {"trace_hash": "0" * 64}
    with pytest.raises(DerivationIntegrityError):
        derive_evidence(registry, [h], "OBSERVATION", "1", {}, {"x": 1})


def test_16_unordered_semantics_are_deterministic():
    registry = _registry("a", "b")
    hashes = list(registry.snapshot())
    left = derive_evidence(registry, hashes, "AGGREGATION", "1", {}, {"n": 2})
    right = derive_evidence(registry, list(reversed(hashes)), "AGGREGATION", "1", {}, {"n": 2})
    assert left == right


def test_17_ordered_semantics_are_explicit():
    registry = _registry("a", "b")
    hashes = list(registry.snapshot())
    left = derive_evidence(registry, hashes, "COMPARISON", "1", {"ordered": True}, {"order": hashes})
    right = derive_evidence(registry, list(reversed(hashes)), "COMPARISON", "1", {"ordered": True}, {"order": list(reversed(hashes))})
    assert left.derived_evidence_hash != right.derived_evidence_hash


def test_18_duplicate_input_semantics():
    registry = _registry("a")
    h = next(iter(registry.snapshot()))
    one = derive_evidence(registry, [h], "AGGREGATION", "1", {}, {"n": 1})
    two = derive_evidence(registry, [h, h], "AGGREGATION", "1", {}, {"n": 2})
    assert one.derived_evidence_hash != two.derived_evidence_hash


def test_19_canonical_parameter_serialization():
    registry = _registry("a")
    h = next(iter(registry.snapshot()))
    a = derive_evidence(registry, [h], "OBSERVATION", "1", {"b": 2, "a": 1}, {"x": 1})
    b = derive_evidence(registry, [h], "OBSERVATION", "1", {"a": 1, "b": 2}, {"x": 1})
    assert a == b


def test_20_equivalent_analysis_has_identical_hash():
    registry = _registry("a")
    h = next(iter(registry.snapshot()))
    a = derive_evidence(registry, [h], "OBSERVATION", "1", {}, {"x": 1})
    b = derive_evidence(registry, [h], "OBSERVATION", "1", {}, {"x": 1})
    assert a.derived_evidence_hash == b.derived_evidence_hash


def test_21_distinct_analysis_cannot_collapse():
    registry = _registry("a")
    h = next(iter(registry.snapshot()))
    a = derive_evidence(registry, [h], "OBSERVATION", "1", {}, {"x": 1})
    b = derive_evidence(registry, [h], "COMPARISON", "1", {}, {"x": 1})
    assert a.derived_evidence_hash != b.derived_evidence_hash


def test_22_payload_tampering_detected():
    registry = _registry("a")
    h = next(iter(registry.snapshot()))
    artifact = derive_evidence(registry, [h], "OBSERVATION", "1", {}, {"x": 1})
    with pytest.raises(DerivationIntegrityError):
        artifact.__class__(artifact.source_hashes, artifact.analysis_type, artifact.algorithm_version, artifact.parameters, {"x": 2}, artifact.provenance, artifact.derived_evidence_hash)


def test_23_source_substitution_rejected():
    registry = _registry("a", "b")
    hashes = list(registry.snapshot())
    artifact = derive_evidence(registry, hashes[:1], "OBSERVATION", "1", {}, {"x": 1})
    with pytest.raises(DerivationIntegrityError):
        artifact.verify(registry, source_hashes=hashes[1:])


def test_24_runtime_metadata_injection_rejected():
    registry = _registry("a")
    h = next(iter(registry.snapshot()))
    with pytest.raises(DerivationIntegrityError):
        derive_evidence(registry, [h], "OBSERVATION", "1", {"timestamp": 1}, {"x": 1})
    with pytest.raises(DerivationIntegrityError):
        derive_evidence(registry, [h], "OBSERVATION", "1", {}, {"hostname": "x"})


def test_25_no_filesystem_network_or_domain_dependency():
    registry = _registry("a")
    h = next(iter(registry.snapshot()))
    artifact = derive_evidence(registry, [h], "OBSERVATION", "1", {}, {"x": 1})
    assert artifact
    import jamp.research.derivation as derivation
    assert "socket" not in derivation.__dict__
    assert "requests" not in derivation.__dict__


def test_26_cross_runtime_deterministic_reproduction():
    registry = _registry("a", "b")
    hashes = list(registry.snapshot())
    artifact = derive_evidence(registry, hashes, "AGGREGATION", "1", {"ordered": False}, {"mean": 1})
    exported = artifact.export()
    recreated = derive_evidence(registry, exported["source_hashes"], exported["analysis_type"], exported["algorithm_version"], exported["parameters"], exported["result"])
    assert recreated.derived_evidence_hash == artifact.derived_evidence_hash
