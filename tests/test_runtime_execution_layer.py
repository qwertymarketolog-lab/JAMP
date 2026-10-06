import hashlib
import json
from pathlib import Path

import pytest

from src.jamp.runtime import (
    CapabilityResolver,
    EvidenceGate,
    ModelSelector,
    ProvenanceTracker,
    TaskClassifier,
)

CORE = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
AID = 11369355096
SHA = "7785cbd5ae19704473b385b8b21ddbdf7cd9eeb06aee56ce0f66e7da7592f1f1"


def blob_sha(data):
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def fixture():
    return json.loads(
        (Path(__file__).parent / "fixtures/runtime_evidence_projection.json").read_text()
    )


def test_frozen_core_blob_is_exact():
    assert blob_sha(Path("src/jamp/run.py").read_bytes()) == CORE


def test_source_identity():
    data = fixture()
    assert data["source"]["artifact_id"] == AID
    assert data["source"]["sha256"] == SHA
    assert data["frozen_core_blob"] == CORE
    assert len(data["models"]) == 17


def test_counts_and_refusal():
    data = fixture()
    gate = EvidenceGate(
        {
            "contract_version": "jamp-17-capability-v1",
            "canonical_manifest_sha256": data["source"]["manifest_sha256"],
            "frozen_core_blob": CORE,
            "expected_models": 17,
            "executed_models": 17,
            "expected_checks": 170,
            "executed_checks": 170,
            "models": data["models"],
        }
    )
    resolver = CapabilityResolver()
    selector = ModelSelector()
    expected = {
        "search_and_extraction": 12,
        "tool_execution_agent": 7,
        "long_context_analysis": 0,
        "strict_compliance_safety": 2,
    }
    for task, count in expected.items():
        eligible = gate.get_eligible_models(resolver.get_required_capabilities(task))
        assert len(eligible) == count
        action, model = selector.select_model(eligible, task)
        assert action == ("REFUSE" if count == 0 else "EXECUTE")
        assert model == "ZERO_ELIGIBLE_MODELS" if count == 0 else True


def test_classifier_fail_closed():
    classifier = TaskClassifier()
    assert classifier.classify({"classification_entropy": 0.86}) == "strict_compliance_safety"
    assert classifier.classify({"token_count": 16001}) == "long_context_analysis"
    with pytest.raises(ValueError):
        classifier.classify({"intent": "unknown"})


def test_refusal_provenance():
    trace = ProvenanceTracker().create_trace(
        "long_context_analysis",
        ["C03", "C08"],
        "REFUSE",
        "ZERO_ELIGIBLE_MODELS",
        0,
    )
    assert trace["status"] == "REFUSE"
    assert trace["frozen_core_state"] == {"blob": CORE, "delta": 0}
    assert trace["gate_evaluator"]["evidence_base_sha256"] == SHA
    assert "refusal_details" in trace
