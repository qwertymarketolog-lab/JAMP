import hashlib
import json
from copy import deepcopy


def canonical(value):
    if isinstance(value, dict):
        return {key: canonical(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        items = [canonical(item) for item in value]
        if all(isinstance(item, dict) and "id" in item for item in items):
            return sorted(items, key=lambda item: item["id"])
        return items
    return value


def canonical_hash(value):
    payload = json.dumps(
        canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def map_signal(normalized):
    atom = {
        "id": "O1",
        "content": normalized["payload"]["content"],
        "type": "observation",
    }
    return {
        "root": {"id": "O0", "type": "observation"},
        "source_ref": normalized["source_ref"],
        "atoms": [atom],
    }


def reconstruct(mapped):
    return {
        "source_ref": mapped["source_ref"],
        "content": mapped["atoms"][0]["content"],
    }


def test_mapping_is_deterministic():
    normalized = {
        "source_ref": "sha256:s",
        "payload": {"content": "X"},
    }
    assert map_signal(normalized) == map_signal(normalized)


def test_lossless_fixture_has_canonical_equivalence():
    normalized = {"source_ref": "sha256:s", "payload": {"content": "X"}}
    mapped = map_signal(normalized)
    source = {"source_ref": "sha256:s", "content": "X"}
    assert canonical_hash(reconstruct(mapped)) == canonical_hash(source)


def test_single_atom_mutation_changes_identity():
    normalized = {"source_ref": "sha256:s", "payload": {"content": "X"}}
    baseline = map_signal(normalized)
    mutated = deepcopy(baseline)
    mutated["atoms"][0]["content"] = "Y"

    assert canonical_hash(mutated) != canonical_hash(baseline)
    assert baseline["source_ref"] == mutated["source_ref"]
