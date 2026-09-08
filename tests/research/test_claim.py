"""P20.4 acceptance and adversarial contract: Hypothesis & Claim Verification.

Test-first contract. All 30 gates remain unchanged; fixtures use the actual
P19.4 ResearchResult API, P20.3 provenance structure, and frozen-object
mutation semantics.
"""

from dataclasses import FrozenInstanceError

import pytest

from jamp.research.canonical import replay_hash
from jamp.research.composition import compose_results
from jamp.research.derivation import derive_evidence
from jamp.research.registry import ArtifactRegistry
from jamp.research.replay import ReplayTrace, compute_trace_hash
from jamp.research.result import ResearchResult, compute_result_hash
from jamp.research.claim import ClaimIntegrityError, ClaimRuleError, ClaimStatus, compute_claim_hash, evaluate_claim, make_claim


def _result(seed: str, value: int | None = None) -> ResearchResult:
    initial = replay_hash({"seed": seed, "state": "initial"})
    event = replay_hash({"seed": seed, "event": "observation"})
    resulting = replay_hash({"seed": seed, "state": "result"})
    trace_hash = compute_trace_hash(initial, (event,), resulting)
    payload = {"value": len(seed) if value is None else value, "label": seed}
    provenance = {"source": "test", "operation": "fixture", "version": "1"}
    result_hash = compute_result_hash(trace_hash, "measurement", payload, provenance)
    return ResearchResult(trace_hash, "measurement", payload, provenance, result_hash)


def _registry(*seeds: str) -> ArtifactRegistry:
    registry = ArtifactRegistry()
    for seed in seeds:
        result = _result(seed)
        initial = replay_hash({"seed": seed, "state": "initial"})
        event = replay_hash({"seed": seed, "event": "observation"})
        resulting = replay_hash({"seed": seed, "state": "result"})
        trace_hash = compute_trace_hash(initial, (event,), resulting)
        registry.register(result, ReplayTrace(initial, (event,), resulting, trace_hash))
    return registry


def _evidence(registry: ArtifactRegistry, seed: str = "a", *, polarity: str = "SUPPORTED"):
    result_hash = next(h for h in registry.snapshot() if registry.get(h).provenance["source"] == "test" and registry.get(h).result_payload["label"] == seed)
    return derive_evidence(registry, [result_hash], "OBSERVATION", "1", {}, {"polarity": polarity, "value": registry.get(result_hash).result_payload["value"]})


def _claim(registry: ArtifactRegistry, *, statement: str = "A", evidence=None, premises=(), status=None):
    if evidence is None:
        evidence = [_evidence(registry)]
    if status is None:
        status = evaluate_claim(evidence, premises, "EVIDENCE_STATUS")
    return make_claim(registry, statement=statement, claim_type="HYPOTHESIS", premises=premises, evidence=evidence, inference_rule="EVIDENCE_STATUS", rule_version="1", status=status)


def test_01_schema_validity():
    registry = _registry("a")
    claim = _claim(registry)
    assert claim.claim_type == "HYPOTHESIS" and claim.statement == "A"
    assert claim.status in tuple(ClaimStatus)


def test_02_structural_immutability():
    claim = _claim(_registry("a"))
    with pytest.raises(FrozenInstanceError):
        claim.statement = "B"
    with pytest.raises(FrozenInstanceError):
        claim.evidence_refs += ("x",)


def test_03_valid_claim_hash():
    claim = _claim(_registry("a"))
    assert claim.claim_hash == compute_claim_hash(claim.claim_type, claim.statement, claim.premises, claim.evidence_refs, claim.inference_rule, claim.rule_version, claim.status)


def test_04_deterministic_hash_computation():
    args = ("HYPOTHESIS", "A", ({"id": "p1", "status": "SUPPORTED"},), ("a" * 64,), "EVIDENCE_STATUS", "1", "SUPPORTED")
    assert compute_claim_hash(*args) == compute_claim_hash(*args)


def test_05_self_verification():
    assert _claim(_registry("a")).verify(_registry("a")) is True


def test_06_canonical_statement():
    registry = _registry("a")
    a = _claim(registry, statement="  A   implies   B  ")
    b = _claim(registry, statement="A implies B")
    assert a.statement == b.statement and a.claim_hash == b.claim_hash


def test_07_explicit_claim_type():
    registry = _registry("a")
    with pytest.raises(ClaimIntegrityError):
        make_claim(registry, statement="A", claim_type="", premises=(), evidence=[_evidence(registry)], inference_rule="EVIDENCE_STATUS", rule_version="1", status="UNDETERMINED")


def test_08_explicit_rule_version():
    registry = _registry("a")
    with pytest.raises(ClaimRuleError):
        make_claim(registry, statement="A", claim_type="HYPOTHESIS", premises=(), evidence=[_evidence(registry)], inference_rule="EVIDENCE_STATUS", rule_version="", status="SUPPORTED")


def test_09_registry_backed_evidence_only():
    with pytest.raises(ClaimIntegrityError):
        make_claim(_registry("a"), statement="A", claim_type="HYPOTHESIS", premises=(), evidence=["0" * 64], inference_rule="EVIDENCE_STATUS", rule_version="1", status="UNDETERMINED")


def test_10_unknown_evidence_rejected():
    with pytest.raises(ClaimIntegrityError):
        make_claim(_registry("a"), statement="A", claim_type="HYPOTHESIS", premises=(), evidence=["f" * 64], inference_rule="EVIDENCE_STATUS", rule_version="1", status="UNDETERMINED")


def test_11_evidence_integrity_verified():
    registry = _registry("a")
    evidence = _evidence(registry)
    object.__setattr__(registry._artifacts[evidence.source_hashes[0]].result, "result_hash", "0" * 64)
    with pytest.raises(ClaimIntegrityError):
        _claim(registry, evidence=evidence)


def test_12_complete_provenance_preserved():
    registry = _registry("a")
    evidence = _evidence(registry)
    claim = _claim(registry, evidence=[evidence])
    assert claim.provenance["evidence"][evidence.derived_evidence_hash]["source_hashes"] == evidence.source_hashes


def test_13_recursive_source_provenance_preserved():
    registry = _registry("a", "b")
    hashes = list(registry.snapshot())
    composition = compose_results(registry, hashes)
    evidence = derive_evidence(registry, [composition], "AGGREGATION", "1", {}, {"polarity": "SUPPORTED"})
    claim = _claim(registry, evidence=[evidence])
    leaf = claim.provenance["evidence"][evidence.derived_evidence_hash]["provenance"]["sources"][composition.composition_hash]["leaves"]
    assert len(leaf) == len(hashes) and all(item["trace_hash"] for item in leaf)


def test_14_premise_integrity():
    with pytest.raises(ClaimIntegrityError):
        _claim(_registry("a"), premises=({"status": "NOT_A_STATUS"},))


def test_15_evidence_substitution_rejected():
    registry = _registry("a", "b")
    first, second = _evidence(registry, "a"), _evidence(registry, "b")
    claim = _claim(registry, evidence=[first])
    with pytest.raises(ClaimIntegrityError):
        claim.verify(registry, evidence=[second])


def test_16_evidence_tampering_detected():
    registry = _registry("a")
    evidence = _evidence(registry)
    claim = _claim(registry, evidence=[evidence])
    tampered = object.__new__(type(evidence))
    object.__setattr__(tampered, "source_hashes", evidence.source_hashes)
    object.__setattr__(tampered, "analysis_type", evidence.analysis_type)
    object.__setattr__(tampered, "algorithm_version", evidence.algorithm_version)
    object.__setattr__(tampered, "parameters", evidence.parameters)
    object.__setattr__(tampered, "result", {"polarity": "REFUTED"})
    object.__setattr__(tampered, "provenance", evidence.provenance)
    object.__setattr__(tampered, "derived_evidence_hash", evidence.derived_evidence_hash)
    with pytest.raises(ClaimIntegrityError):
        claim.verify(registry, evidence=[tampered])


def test_17_explicit_inference_rule_required():
    with pytest.raises(ClaimRuleError):
        make_claim(_registry("a"), statement="A", claim_type="HYPOTHESIS", premises=(), evidence=[_evidence(_registry("a"))], inference_rule="", rule_version="1", status="UNDETERMINED")


def test_18_missing_premise_rejected_for_premise_rule():
    registry = _registry("a")
    with pytest.raises(ClaimIntegrityError):
        make_claim(registry, statement="A", claim_type="HYPOTHESIS", premises=(), evidence=[_evidence(registry)], inference_rule="PREMISE_CONJUNCTION", rule_version="1", status="SUPPORTED")


def test_19_unsupported_inference_rejected():
    registry = _registry("a")
    with pytest.raises(ClaimRuleError):
        make_claim(registry, statement="A", claim_type="HYPOTHESIS", premises=(), evidence=[_evidence(registry)], inference_rule="MAGIC_RULE", rule_version="1", status="SUPPORTED")


def test_20_supported_is_deterministic():
    evidence = [_evidence(_registry("a"), polarity="SUPPORTED")]
    assert evaluate_claim(evidence, (), "EVIDENCE_STATUS") == ClaimStatus.SUPPORTED
    assert evaluate_claim(evidence, (), "EVIDENCE_STATUS") == evaluate_claim(evidence, (), "EVIDENCE_STATUS")


def test_21_refuted_is_deterministic():
    assert evaluate_claim([_evidence(_registry("a"), polarity="REFUTED")], (), "EVIDENCE_STATUS") == ClaimStatus.REFUTED


def test_22_undetermined_is_first_class():
    assert evaluate_claim([], (), "EVIDENCE_STATUS") == ClaimStatus.UNDETERMINED


def test_23_contradicted_preserves_conflict():
    registry = _registry("a", "b")
    evidence = [_evidence(registry, "a", polarity="SUPPORTED"), _evidence(registry, "b", polarity="REFUTED")]
    assert evaluate_claim(evidence, (), "EVIDENCE_STATUS") == ClaimStatus.CONTRADICTED
    assert len(_claim(registry, evidence=evidence).evidence_refs) == 2


def test_24_claim_payload_tampering_detected():
    claim = _claim(_registry("a"))
    with pytest.raises(ClaimIntegrityError):
        type(claim)(claim.claim_type, "B", claim.premises, claim.evidence_refs, claim.inference_rule, claim.rule_version, claim.status, claim.provenance, claim.claim_hash)


def test_25_rule_substitution_rejected():
    claim = _claim(_registry("a"))
    with pytest.raises(ClaimIntegrityError):
        claim.verify(_registry("a"), inference_rule="PREMISE_CONJUNCTION")


def test_26_parameter_injection_rejected():
    registry = _registry("a")
    evidence = _evidence(registry)
    with pytest.raises(ClaimIntegrityError):
        _claim(registry, evidence=[evidence], premises=({"id": "p1", "status": "SUPPORTED", "timestamp": 1},))


def test_27_runtime_metadata_injection_rejected():
    registry = _registry("a")
    evidence = _evidence(registry)
    with pytest.raises(ClaimIntegrityError):
        make_claim(registry, statement="A", claim_type="HYPOTHESIS", premises=({"id": "p1", "status": "SUPPORTED", "hostname": "x"},), evidence=[evidence], inference_rule="EVIDENCE_STATUS", rule_version="1", status="SUPPORTED")


def test_28_duplicate_evidence_semantics_are_deterministic():
    registry = _registry("a")
    evidence = _evidence(registry)
    one, two = _claim(registry, evidence=[evidence]), _claim(registry, evidence=[evidence, evidence])
    assert two.evidence_refs == one.evidence_refs and two.claim_hash == one.claim_hash


def test_29_cross_runtime_reproduction():
    registry = _registry("a")
    claim = _claim(registry)
    exported = claim.export()
    recreated = make_claim(registry, statement=exported["statement"], claim_type=exported["claim_type"], premises=exported["premises"], evidence=[_evidence(registry)], inference_rule=exported["inference_rule"], rule_version=exported["rule_version"], status=exported["status"])
    assert recreated.claim_hash == claim.claim_hash


def test_30_zero_io_and_domain_contamination():
    claim = _claim(_registry("a"))
    assert claim
    import jamp.research.claim as claim_module
    assert "socket" not in claim_module.__dict__ and "requests" not in claim_module.__dict__ and "jamp.domain" not in claim_module.__dict__
