"""P21.2 Research Session / Experiment Ledger acceptance tests.

The test module is intentionally created before the implementation. Each test
maps to one frozen acceptance gate from the locked P21.2 contract.
"""

import hashlib
import importlib
import inspect
import json
import os
import socket
from dataclasses import FrozenInstanceError, is_dataclass
from types import MappingProxyType

import pytest


MODULE = "jamp.research.session"


def _load():
    return importlib.import_module(MODULE)


def _api():
    mod = _load()
    return mod, getattr(mod, "ResearchSession"), getattr(mod, "SessionArtifact")


def _artifact(kind, value):
    _, Artifact, _ = _api() if False else (None, None, None)
    # Filled by implementation-compatible helper below after import.
    mod = _load()
    cls = getattr(mod, "SessionArtifact")
    return cls(kind=kind, artifact_hash=value)


def _session(artifacts=None, metadata=None, status="OPEN"):
    mod = _load()
    cls = mod.ResearchSession
    return cls.create(
        metadata={} if metadata is None else metadata,
        artifacts=[] if artifacts is None else artifacts,
        status=status,
    )


def _hash(label):
    return hashlib.sha256(label.encode()).hexdigest()


def test_gate_01_schema_validity():
    s = _session([_artifact("question", _hash("q1"))])
    assert s.verify() is True
    assert isinstance(s.session_hash, str) and len(s.session_hash) == 64


def test_gate_02_immutable_record():
    s = _session()
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        s.status = "CLOSED"


def test_gate_03_valid_session_hash():
    s = _session(metadata={"title": "x"})
    assert s.session_hash == s.compute_session_hash()


def test_gate_04_deterministic_identity():
    a = _session([_artifact("question", _hash("q"))], {"b": 2, "a": 1})
    b = _session([_artifact("question", _hash("q"))], {"a": 1, "b": 2})
    assert a.session_hash == b.session_hash


def test_gate_05_self_verification():
    s = _session()
    assert s.verify() is True
    assert s.with_tampered_hash("0" * 64).verify() is False


def test_gate_06_explicit_metadata():
    s = _session(metadata={"title": "investigation", "purpose": "test"})
    assert dict(s.metadata)["title"] == "investigation"


def test_gate_07_explicit_object_indexes():
    s = _session([
        _artifact("question", _hash("q")),
        _artifact("plan", _hash("p")),
        _artifact("execution", _hash("e")),
        _artifact("result", _hash("r")),
        _artifact("interpretation", _hash("i")),
        _artifact("consensus", _hash("c")),
        _artifact("revision", _hash("v")),
    ])
    assert set(s.indexes) == {"question", "plan", "execution", "result", "interpretation", "consensus", "revision"}


def test_gate_08_valid_status():
    assert _session(status="OPEN").status == "OPEN"
    with pytest.raises(ValueError):
        _session(status="UNKNOWN")


def test_gate_09_runtime_independent_identity():
    s = _session([_artifact("question", _hash("q"))])
    payload = s.canonical_bytes()
    assert b"id(" not in payload and b"0x" not in payload


def test_gate_10_canonical_serialization():
    s = _session([_artifact("question", _hash("q"))], {"z": [2, 1], "a": True})
    assert s.canonical_bytes() == s.canonical_bytes()
    json.loads(s.export())


def test_gate_11_question_binding():
    s = _session([_artifact("question", _hash("q"))])
    assert s.indexes["question"] == (_hash("q"),)


def test_gate_12_plan_binding():
    s = _session([_artifact("plan", _hash("p"))])
    assert s.indexes["plan"] == (_hash("p"),)


def test_gate_13_execution_binding():
    s = _session([_artifact("execution", _hash("e"))])
    assert s.indexes["execution"] == (_hash("e"),)


def test_gate_14_result_binding():
    s = _session([_artifact("result", _hash("r"))])
    assert s.indexes["result"] == (_hash("r"),)


def test_gate_15_interpretation_binding():
    s = _session([_artifact("interpretation", _hash("i"))])
    assert s.indexes["interpretation"] == (_hash("i"),)


def test_gate_16_consensus_binding():
    s = _session([_artifact("consensus", _hash("c"))])
    assert s.indexes["consensus"] == (_hash("c"),)


def test_gate_17_revision_binding():
    s = _session([_artifact("revision", _hash("v"))])
    assert s.indexes["revision"] == (_hash("v"),)


def test_gate_18_unknown_artifact_rejected():
    with pytest.raises(ValueError):
        _session([_artifact("unknown", _hash("x"))])


def test_gate_19_artifact_integrity_verified():
    mod = _load()
    with pytest.raises((ValueError, TypeError)):
        mod.ResearchSession.create(metadata={}, artifacts=[{"kind": "question", "artifact_hash": "bad"}], status="OPEN")


def test_gate_20_artifact_substitution_rejected():
    s = _session([_artifact("question", _hash("q"))])
    with pytest.raises((ValueError, TypeError)):
        s.replace_artifact("question", _hash("other"))


def test_gate_21_membership_explicit():
    s = _session([_artifact("question", _hash("q"))])
    assert s.contains("question", _hash("q")) is True
    assert s.contains("question", _hash("x")) is False


def test_gate_22_duplicate_references_deterministic():
    a = _session([_artifact("question", _hash("q")), _artifact("question", _hash("q"))])
    b = _session([_artifact("question", _hash("q"))])
    assert a.session_hash == b.session_hash


def test_gate_23_semantic_ordering_deterministic():
    q1, q2 = _hash("q1"), _hash("q2")
    a = _session([_artifact("question", q2), _artifact("question", q1)])
    b = _session([_artifact("question", q1), _artifact("question", q2)])
    assert a.indexes["question"] == b.indexes["question"]


def test_gate_24_unordered_permutation_independent():
    artifacts = [_artifact("result", _hash("r1")), _artifact("result", _hash("r2"))]
    assert _session(artifacts).session_hash == _session(list(reversed(artifacts))).session_hash


def test_gate_25_complete_provenance_preserved():
    q, p, e, r = (_hash(x) for x in ("q", "p", "e", "r"))
    s = _session([_artifact("question", q), _artifact("plan", p), _artifact("execution", e), _artifact("result", r)])
    assert s.provenance() == {"question": (q,), "plan": (p,), "execution": (e,), "result": (r,)}


def test_gate_26_recursive_provenance_preserved():
    s = _session([_artifact("result", _hash("r"))])
    chain = s.provenance_chain(_hash("r"))
    assert chain["result"] == _hash("r")


def test_gate_27_historical_objects_never_mutated():
    artifact = _artifact("result", _hash("r"))
    s = _session([artifact])
    assert artifact.artifact_hash == _hash("r")
    assert s.contains("result", _hash("r"))


def test_gate_28_session_cannot_rewrite_upstream_identity():
    s = _session([_artifact("result", _hash("r"))])
    with pytest.raises((AttributeError, TypeError, ValueError)):
        s.rewrite_upstream("result", _hash("x"))


def test_gate_29_equivalent_sessions_same_hash():
    a = _session([_artifact("question", _hash("q"))], {"a": 1, "b": 2})
    b = _session([_artifact("question", _hash("q"))], {"b": 2, "a": 1})
    assert a.session_hash == b.session_hash


def test_gate_30_material_difference_distinct():
    a = _session([_artifact("question", _hash("q1"))])
    b = _session([_artifact("question", _hash("q2"))])
    assert a.session_hash != b.session_hash


def test_gate_31_deterministic_export():
    s = _session([_artifact("question", _hash("q"))])
    assert s.export() == s.export()


def test_gate_32_deterministic_import_verification():
    s = _session([_artifact("question", _hash("q"))])
    restored = _load().ResearchSession.import_(s.export())
    assert restored.verify() and restored.session_hash == s.session_hash


def test_gate_33_complete_investigation_reconstruction():
    s = _session([_artifact("question", _hash("q")), _artifact("plan", _hash("p")), _artifact("result", _hash("r"))])
    restored = _load().ResearchSession.import_(s.export())
    assert restored.indexes == s.indexes and restored.provenance() == s.provenance()


def test_gate_34_cross_runtime_byte_identity():
    s = _session([_artifact("question", _hash("q"))], {"x": "unicode π"})
    assert hashlib.sha256(s.canonical_bytes()).hexdigest() == s.session_hash


def test_gate_35_session_payload_tampering_detected():
    s = _session(metadata={"x": 1})
    payload = json.loads(s.export())
    payload["metadata"]["x"] = 2
    assert _load().ResearchSession.from_export_payload(payload).verify() is False


def test_gate_36_artifact_substitution_attack_blocked():
    s = _session([_artifact("result", _hash("r"))])
    payload = json.loads(s.export())
    payload["indexes"]["result"][0] = _hash("evil")
    assert _load().ResearchSession.from_export_payload(payload).verify() is False


def test_gate_37_artifact_mutation_detected():
    s = _session([_artifact("result", _hash("r"))])
    tampered = s.with_artifact_hash("result", _hash("mutated"))
    assert tampered.verify() is False


def test_gate_38_runtime_metadata_injection_rejected():
    with pytest.raises(ValueError):
        _session(metadata={"runtime": {"pid": 123, "host": "x"}})


def test_gate_39_session_dependency_cycle_rejected():
    with pytest.raises(ValueError):
        _session([_artifact("session", _hash("nested-session"))])


def test_gate_40_zero_io_network_domain_contamination():
    src = inspect.getsource(_load())
    assert "jamp.domain" not in src
    assert "socket" not in src
    assert "requests" not in src
    assert "urllib" not in src
    assert "open(" not in src


def test_meta_gate_all_40_named():
    names = [n for n, obj in globals().items() if n.startswith("test_gate_") and callable(obj)]
    assert len(names) == 40
