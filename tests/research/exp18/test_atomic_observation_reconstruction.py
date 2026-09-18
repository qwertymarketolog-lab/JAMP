""""EXP-18.R1 lossless reconstruction harness.

This module is intentionally test-local: it defines a deterministic reference
decomposition/reconstruction pair for fixed mock observations.  It does not
introduce a runtime parser or production API.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any


def canonicalize(value: Any) -> Any:
    """Return a deterministic structural representation."""
    if isinstance(value, dict):
        return {key: canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        normalized = [canonicalize(item) for item in value]
        if all(isinstance(item, dict) and "id" in item for item in normalized):
            return sorted(normalized, key=lambda item: item["id"])
        return normalized
    return value


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        canonicalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def make_observation() -> dict[str, Any]:
    return {
        "id": "O0",
        "type": "observation",
        "content": "Object X changed after Y",
        "provenance": {
            "source_ref": "sha256:fixture-source",
            "operator": {"id": "exp18.reference", "version": "0.1"},
        },
        "atoms": [
            {"id": "O1", "content": "Object X", "type": "entity"},
            {"id": "O2", "content": "changed", "type": "event"},
            {"id": "O3", "content": "after", "type": "relation"},
            {"id": "O4", "content": "Y", "type": "entity"},
            {"id": "O5", "content": "O1 != O4", "type": "constraint"},
            {"id": "O6", "content": "O2 follows O4", "type": "relation"},
        ],
        "edges": [
            {"id": "E1", "from": "O1", "to": "O2", "type": "subject"},
            {"id": "E2", "from": "O2", "to": "O4", "type": "object"},
            {"id": "E3", "from": "O3", "to": "O6", "type": "qualifier"},
            {"id": "E4", "from": "O5", "to": "O1", "type": "references"},
            {"id": "E5", "from": "O5", "to": "O4", "type": "references"},
        ],
    }


def decompose(observation: dict[str, Any]) -> dict[str, Any]:
    """Deterministically extract the lossless atomic representation."""
    return {
        "root": {
            "id": observation["id"],
            "type": observation["type"],
            "content": observation["content"],
        },
        "provenance": deepcopy(observation["provenance"]),
        "atoms": deepcopy(observation["atoms"]),
        "edges": deepcopy(observation["edges"]),
    }


def reconstruct(parts: dict[str, Any]) -> dict[str, Any]:
    """Deterministically rebuild the canonical observation structure."""
    return {
        "id": parts["root"]["id"],
        "type": parts["root"]["type"],
        "content": parts["root"]["content"],
        "provenance": deepcopy(parts["provenance"]),
        "atoms": deepcopy(parts["atoms"]),
        "edges": deepcopy(parts["edges"]),
    }


def test_reconstruction_is_lossless_by_canonical_hash():
    source = make_observation()

    reconstructed = reconstruct(decompose(source))

    assert canonical_hash(reconstructed) == canonical_hash(source)


def test_reconstruction_is_invariant_to_atom_permutation():
    source = make_observation()
    parts = decompose(source)
    parts["atoms"] = list(reversed(parts["atoms"]))

    reconstructed = reconstruct(parts)

    assert canonical_hash(reconstructed) == canonical_hash(source)


def test_mutating_one_atom_changes_hash_and_localizes_difference():
    source = make_observation()
    baseline_parts = decompose(source)
    mutated_parts = deepcopy(baseline_parts)

    mutated_parts["atoms"][3]["content"] = "Z"

    baseline = reconstruct(baseline_parts)
    mutated = reconstruct(mutated_parts)

    assert canonical_hash(mutated) != canonical_hash(baseline)

    baseline_atoms = {atom["id"]: atom for atom in baseline["atoms"]}
    mutated_atoms = {atom["id"]: atom for atom in mutated["atoms"]}

    changed_ids = {
        atom_id for atom_id in baseline_atoms if baseline_atoms[atom_id] != mutated_atoms[atom_id]
    }

    assert changed_ids == {"O4"}
    assert baseline["provenance"] == mutated["provenance"]
    assert baseline["edges"] == mutated["edges"]


def test_reconstruction_preserves_provenance():
    source = make_observation()

    reconstructed = reconstruct(decompose(source))

    assert reconstructed["provenance"] == source["provenance"]
