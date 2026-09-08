"""P20.1 Immutable Artifact Registry — contract and adversarial gates."""

from __future__ import annotations

import importlib
import inspect
from types import MappingProxyType

import pytest

from jamp.research.replay import ReplayTrace, compute_trace_hash
from jamp.research.result import compute_result_hash, project_result
from jamp.research.registry import ArtifactRegistry, RegistryIntegrityError


STATE_HASH = "b" * 64
TRACE_HASH = compute_trace_hash(STATE_HASH, (), STATE_HASH)
RESULT_HASH = "c" * 64


def make_result(*, payload=None, provenance=None):
    trace = ReplayTrace(
        initial_state_hash=STATE_HASH,
        ordered_event_ids=(),
        resulting_state_hash=STATE_HASH,
        trace_hash=TRACE_HASH,
    )
    return project_result(
        trace,
        "finding",
        payload if payload is not None else {"answer": 42},
        provenance if provenance is not None else {
            "source": "test",
            "operation": "p20.1",
            "version": "1",
        },
    )


def test_gate_01_schema_validity():
    registry = ArtifactRegistry()
    result = make_result()
    stored = registry.register(result)
    assert stored == result
    assert registry.get(result.result_hash) == result


def test_gate_02_structural_immutability():
    registry = ArtifactRegistry()
    result = make_result()
    registry.register(result)
    with pytest.raises(TypeError):
        registry.index[result.result_hash] = result
    with pytest.raises(TypeError):
        result.result_payload["answer"] = 7


def test_gate_03_content_addressing_consistency():
    registry = ArtifactRegistry()
    result = make_result()
    registry.register(result)
    assert registry.contains(result.result_hash)
    assert not registry.contains("d" * 64)
    assert result.result_hash == compute_result_hash(
        result.trace_hash, result.result_type, result.result_payload, result.provenance
    )


def test_gate_04_deterministic_hash_lookup():
    registry = ArtifactRegistry()
    result = make_result()
    registry.register(result)
    assert registry.get(result.result_hash) is result
    assert registry.get(result.result_hash) == result
    with pytest.raises(KeyError):
        registry.get("d" * 64)


def test_gate_05_self_verification_of_stored_artifact():
    registry = ArtifactRegistry()
    result = make_result()
    registry.register(result)
    assert registry.verify(result.result_hash) is True


def test_gate_06_empty_registry_handling():
    registry = ArtifactRegistry()
    assert len(registry) == 0
    assert registry.snapshot() == MappingProxyType({})


def test_gate_07_duplicate_registration_is_idempotent():
    registry = ArtifactRegistry()
    result = make_result()
    assert registry.register(result) is result
    assert registry.register(result) is result
    assert len(registry) == 1


def test_gate_08_result_payload_tampering_is_rejected():
    registry = ArtifactRegistry()
    result = make_result()
    registry.register(result)
    with pytest.raises(TypeError):
        result.result_payload["answer"] = 99
    assert registry.verify(result.result_hash) is True


def test_gate_09_trace_or_index_tampering_is_rejected():
    registry = ArtifactRegistry()
    result = make_result()
    registry.register(result)
    with pytest.raises(TypeError):
        registry.index[result.result_hash] = MappingProxyType({"trace_hash": "d" * 64})
    with pytest.raises(RegistryIntegrityError):
        registry.verify_index(result.result_hash, "d" * 64)


def test_gate_10_hash_collision_rejection():
    registry = ArtifactRegistry()
    result = make_result()
    registry.register(result)
    forged = object.__new__(type(result))
    object.__setattr__(forged, "trace_hash", result.trace_hash)
    object.__setattr__(forged, "result_type", "finding")
    object.__setattr__(forged, "result_payload", MappingProxyType({"answer": 999}))
    object.__setattr__(forged, "provenance", result.provenance)
    object.__setattr__(forged, "result_hash", result.result_hash)
    with pytest.raises(RegistryIntegrityError):
        registry.register(forged)


def test_gate_11_provenance_mismatch_rejection():
    registry = ArtifactRegistry()
    result = make_result()
    registry.register(result)
    bad = object.__new__(type(result))
    object.__setattr__(bad, "trace_hash", result.trace_hash)
    object.__setattr__(bad, "result_type", result.result_type)
    object.__setattr__(bad, "result_payload", result.result_payload)
    object.__setattr__(bad, "provenance", MappingProxyType({
        "source": "tampered", "operation": "p20.1", "version": "1"
    }))
    object.__setattr__(bad, "result_hash", result.result_hash)
    with pytest.raises(RegistryIntegrityError):
        registry.register(bad)


def test_gate_12_corrupted_artifact_retrieval_is_rejected():
    registry = ArtifactRegistry()
    result = make_result()
    registry.register(result)
    assert registry.get(result.result_hash).verify() is True
    with pytest.raises(RegistryIntegrityError):
        registry.verify_index(result.result_hash, "e" * 64)


def test_gate_13_insertion_order_independence():
    first = make_result(payload={"answer": 1})
    second = make_result(payload={"answer": 2})
    left = ArtifactRegistry()
    right = ArtifactRegistry()
    left.register(first)
    left.register(second)
    right.register(second)
    right.register(first)
    assert left.snapshot() == right.snapshot()


def test_gate_14_retrieval_determinism_across_instances():
    result = make_result()
    left = ArtifactRegistry()
    right = ArtifactRegistry()
    left.register(result)
    right.register(result)
    assert left.get(result.result_hash) == right.get(result.result_hash)
    assert left.index == right.index


def test_gate_15_canonical_serialization_enforcement():
    left = make_result(payload={"b": 2, "a": 1})
    right = make_result(payload={"a": 1, "b": 2})
    assert left.result_hash == right.result_hash
    registry = ArtifactRegistry()
    registry.register(left)
    assert registry.get(right.result_hash) == left


def test_gate_16_cross_runtime_independence():
    result = make_result()
    registry = ArtifactRegistry()
    registry.register(result)
    exported = registry.export()
    restored = ArtifactRegistry.from_export(exported)
    assert restored.snapshot() == registry.snapshot()
    assert restored.get(result.result_hash) == result


def test_gate_17_forbidden_runtime_metadata_exclusion():
    source = inspect.getsource(importlib.import_module("jamp.research.registry"))
    forbidden = ("timestamp", "uuid", "memory_address", "environment", "local_path", "hostname", "pid")
    assert not any(token in source for token in forbidden)


def test_gate_18_zero_filesystem_dependency():
    source = inspect.getsource(importlib.import_module("jamp.research.registry"))
    assert "open(" not in source
    assert "pathlib" not in source
    assert "os." not in source


def test_gate_19_zero_network_dependency():
    source = inspect.getsource(importlib.import_module("jamp.research.registry"))
    assert "socket" not in source
    assert "urllib" not in source
    assert "requests" not in source
    assert "httpx" not in source


def test_gate_20_no_jamp_domain_imports():
    source = inspect.getsource(importlib.import_module("jamp.research.registry"))
    assert "jamp.domain" not in source


def test_gate_21_historical_baseline_reference_is_not_mutated():
    module = importlib.import_module("jamp.research.registry")
    assert module.__file__.replace("\\", "/").endswith("src/jamp/research/registry.py")


def test_gate_22_research_scope_isolated_from_production_domain():
    source = inspect.getsource(importlib.import_module("jamp.research.registry"))
    assert "from jamp.domain" not in source
    assert "import jamp.domain" not in source
