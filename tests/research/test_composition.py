"""P20.2 Cross-Trajectory Composition — 24 contract and adversarial gates."""

from __future__ import annotations

import hashlib
import importlib
import inspect

import pytest

from jamp.research.canonical import canonical_bytes
from jamp.research.replay import ReplayTrace, compute_trace_hash
from jamp.research.result import project_result
from jamp.research.registry import ArtifactRegistry, RegistryIntegrityError
from jamp.research.composition import (
    CompositionArtifact,
    CompositionIntegrityError,
    compose_results,
    compute_composition_hash,
)


STATE_A = "a" * 64
STATE_B = "b" * 64


def make_result(answer: int, *, state_hash: str = STATE_A):
    trace_hash = compute_trace_hash(state_hash, (), state_hash)
    trace = ReplayTrace(
        initial_state_hash=state_hash,
        ordered_event_ids=(),
        resulting_state_hash=state_hash,
        trace_hash=trace_hash,
    )
    return project_result(
        trace,
        "finding",
        {"answer": answer},
        {"source": "test", "operation": "p20.2", "version": "1"},
    ), trace


def make_registry():
    registry = ArtifactRegistry()
    first, first_trace = make_result(1)
    second, second_trace = make_result(2, state_hash=STATE_B)
    registry.register(first, first_trace)
    registry.register(second, second_trace)
    return registry, first, second


def test_gate_01_schema_validity():
    registry, first, second = make_registry()
    artifact = compose_results(registry, [first.result_hash, second.result_hash])
    assert isinstance(artifact, CompositionArtifact)
    assert artifact.result_hashes == tuple(sorted((first.result_hash, second.result_hash)))
    assert len(artifact.composition_hash) == 64


def test_gate_02_structural_immutability():
    registry, first, second = make_registry()
    artifact = compose_results(registry, [first.result_hash, second.result_hash])
    with pytest.raises(TypeError):
        artifact.semantics["x"] = 1
    with pytest.raises(TypeError):
        artifact.provenance["x"] = 1
    with pytest.raises(TypeError):
        artifact.result_hashes[0] = "x"


def test_gate_03_valid_composition_hash():
    registry, first, second = make_registry()
    artifact = compose_results(registry, [first.result_hash, second.result_hash])
    assert artifact.composition_hash == compute_composition_hash(
        artifact.result_hashes, artifact.semantics
    )


def test_gate_04_deterministic_hash_computation():
    registry, first, second = make_registry()
    left = compose_results(registry, [first.result_hash, second.result_hash])
    right = compose_results(registry, [second.result_hash, first.result_hash])
    assert left.composition_hash == right.composition_hash


def test_gate_05_self_verification():
    registry, first, second = make_registry()
    artifact = compose_results(registry, [first.result_hash, second.result_hash])
    assert artifact.verify(registry) is True


def test_gate_06_empty_input_semantics():
    registry, _, _ = make_registry()
    artifact = compose_results(registry, [])
    assert artifact.result_hashes == ()
    assert artifact.verify(registry) is True


def test_gate_07_every_input_must_be_registered():
    registry, first, _ = make_registry()
    unknown = "d" * 64
    with pytest.raises(CompositionIntegrityError):
        compose_results(registry, [first.result_hash, unknown])


def test_gate_08_unknown_result_hash_rejected():
    registry, _, _ = make_registry()
    with pytest.raises(CompositionIntegrityError):
        compose_results(registry, ["e" * 64])


def test_gate_09_input_result_integrity_verified():
    registry, first, _ = make_registry()
    forged = object.__new__(type(first))
    for field in ("trace_hash", "result_type", "result_payload", "provenance", "result_hash"):
        object.__setattr__(forged, field, getattr(first, field))
    object.__setattr__(forged, "result_payload", {"answer": 999})
    registry._artifacts[first.result_hash] = type(registry._artifacts[first.result_hash])(forged, None)
    with pytest.raises((RegistryIntegrityError, CompositionIntegrityError)):
        compose_results(registry, [first.result_hash])


def test_gate_10_complete_provenance_preservation():
    registry, first, second = make_registry()
    artifact = compose_results(registry, [first.result_hash, second.result_hash])
    assert artifact.provenance[first.result_hash]["source"] == "test"
    assert artifact.provenance[second.result_hash]["operation"] == "p20.2"


def test_gate_11_trace_hashes_preserved_exactly():
    registry, first, second = make_registry()
    artifact = compose_results(registry, [first.result_hash, second.result_hash])
    assert artifact.trace_hashes == {
        first.result_hash: first.trace_hash,
        second.result_hash: second.trace_hash,
    }


def test_gate_12_event_identities_preserved_exactly():
    registry, first, second = make_registry()
    artifact = compose_results(registry, [first.result_hash, second.result_hash])
    assert artifact.event_ids == {first.result_hash: (), second.result_hash: ()}


def test_gate_13_state_anchors_preserved_exactly():
    registry, first, second = make_registry()
    artifact = compose_results(registry, [first.result_hash, second.result_hash])
    assert artifact.state_anchors[first.result_hash] == (STATE_A, STATE_A)
    assert artifact.state_anchors[second.result_hash] == (STATE_B, STATE_B)


def test_gate_14_registry_tampering_detected():
    registry, first, _ = make_registry()
    registry._index[first.result_hash] = {"trace_hash": "f" * 64}
    with pytest.raises((RegistryIntegrityError, CompositionIntegrityError)):
        compose_results(registry, [first.result_hash])


def test_gate_15_input_permutation_independence():
    registry, first, second = make_registry()
    left = compose_results(registry, [first.result_hash, second.result_hash])
    right = compose_results(registry, [second.result_hash, first.result_hash])
    assert left == right


def test_gate_16_duplicate_input_semantics_are_deterministic():
    registry, first, second = make_registry()
    one = compose_results(registry, [first.result_hash, first.result_hash, second.result_hash])
    two = compose_results(registry, [second.result_hash, first.result_hash, first.result_hash])
    assert one == two
    assert one.result_hashes.count(first.result_hash) == 2


def test_gate_17_canonical_payload_ordering():
    registry, first, second = make_registry()
    left = compose_results(registry, [first.result_hash], semantics={"b": 2, "a": 1})
    right = compose_results(registry, [first.result_hash], semantics={"a": 1, "b": 2})
    assert left.composition_hash == right.composition_hash


def test_gate_18_equivalent_compositions_identical_hash():
    registry, first, second = make_registry()
    left = compose_results(registry, [first.result_hash, second.result_hash], semantics={"mode": "meta"})
    right = compose_results(registry, [second.result_hash, first.result_hash], semantics={"mode": "meta"})
    assert left.composition_hash == right.composition_hash


def test_gate_19_distinct_compositions_do_not_silently_collapse():
    registry, first, second = make_registry()
    left = compose_results(registry, [first.result_hash])
    right = compose_results(registry, [second.result_hash])
    assert left.composition_hash != right.composition_hash


def test_gate_20_composition_payload_tampering_rejected():
    registry, first, _ = make_registry()
    artifact = compose_results(registry, [first.result_hash])
    forged = object.__new__(type(artifact))
    for field in ("result_hashes", "semantics", "provenance", "trace_hashes", "event_ids", "state_anchors", "composition_hash"):
        object.__setattr__(forged, field, getattr(artifact, field))
    object.__setattr__(forged, "semantics", {"tampered": True})
    with pytest.raises(CompositionIntegrityError):
        forged.verify(registry)


def test_gate_21_input_result_substitution_rejected():
    registry, first, second = make_registry()
    artifact = compose_results(registry, [first.result_hash])
    forged = object.__new__(type(artifact))
    for field in ("result_hashes", "semantics", "provenance", "trace_hashes", "event_ids", "state_anchors", "composition_hash"):
        object.__setattr__(forged, field, getattr(artifact, field))
    object.__setattr__(forged, "result_hashes", (second.result_hash,))
    with pytest.raises(CompositionIntegrityError):
        forged.verify(registry)


def test_gate_22_runtime_metadata_injection_rejected():
    registry, first, _ = make_registry()
    with pytest.raises((ValueError, TypeError, CompositionIntegrityError)):
        compose_results(registry, [first.result_hash], semantics={"timestamp": "forbidden"})
    source = inspect.getsource(importlib.import_module("jamp.research.composition"))
    forbidden = ("timestamp", "uuid", "memory_address", "environment", "local_path", "hostname", "pid", "process_id")
    assert not any(token in source for token in forbidden)


def test_gate_23_no_filesystem_network_or_domain_dependency():
    source = inspect.getsource(importlib.import_module("jamp.research.composition"))
    forbidden = ("open(", "pathlib", "os.", "socket", "urllib", "requests", "httpx", "jamp.domain")
    assert not any(token in source for token in forbidden)


def test_gate_24_cross_runtime_deterministic_reproduction():
    registry, first, second = make_registry()
    artifact = compose_results(registry, [first.result_hash, second.result_hash], semantics={"mode": "meta"})
    material = {
        "result_hashes": list(artifact.result_hashes),
        "semantics": {key: value for key, value in artifact.semantics.items()},
    }
    expected = hashlib.sha256(canonical_bytes(material)).hexdigest()
    assert artifact.composition_hash == expected
    assert artifact.verify(registry) is True
