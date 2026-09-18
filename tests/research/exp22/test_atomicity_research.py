"""Research-only atomicity checks for EXP-22 observation vectors.

This module does not modify production/runtime behavior or define semantic
acceptance. It probes identity, determinism, composite transparency,
provenance binding, and layer separation using the existing research layer.
"""

from __future__ import annotations

import hashlib
import json

from research.exp22.test_observation_integrity import _observation_identity


def _atom(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_identity_shifts_when_one_atomic_component_changes() -> None:
    base = {"source": "s1", "payload": {"a": 1, "b": 2}}
    changed = {"source": "s1", "payload": {"a": 1, "b": 3}}

    assert _atom(base) != _atom(changed)


def test_unchanged_atomic_component_is_deterministic() -> None:
    value = {"source": "s1", "payload": {"a": 1, "b": 2}}

    assert _atom(value) == _atom(value)


def test_composite_change_is_visible_without_tail_masking() -> None:
    base = {"a": 1, "b": 2, "c": 3}
    changed = {"a": 1, "b": 9, "c": 3}

    base_parts = tuple(_atom(base[key]) for key in ("a", "b", "c"))
    changed_parts = tuple(_atom(changed[key]) for key in ("a", "b", "c"))

    assert base_parts[0] == changed_parts[0]
    assert base_parts[1] != changed_parts[1]
    assert base_parts[2] == changed_parts[2]
    assert base_parts != changed_parts


def test_provenance_binding_remains_source_specific() -> None:
    payload = {"claim": "x"}
    left = _observation_identity("source-a", payload)
    right = _observation_identity("source-b", payload)

    assert left != right


def test_atomization_vector_contains_no_semantic_verdict() -> None:
    observation = {"source": "s1", "payload": {"a": 1}}
    identity = _atom(observation)

    assert "supported" not in identity.lower()
    assert "inconclusive" not in identity.lower()
    assert "refuted" not in identity.lower()
