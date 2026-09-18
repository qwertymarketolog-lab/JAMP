from __future__ import annotations

import hashlib
import json

import pytest

from research.exp19.observation_relation import (
    ObservationRelation,
    compute_edge_hash,
    validate_acyclic_subset,
)


def relation(source: str, target: str, kind: str = "adjacent", params=None):
    return ObservationRelation(
        source_id=source,
        target_id=target,
        relation_type=kind,
        params={} if params is None else params,
    )


# A. Determinism: 20 parametrized tests, each exercising 50 deterministic
# cases, for 1000 canonicalization repetitions in total.
@pytest.mark.parametrize("seed", range(20))
def test_determinism_over_deterministic_graph_set(seed: int) -> None:
    for offset in range(50):
        source = f"atom-{seed}-{offset}"
        target = f"atom-{seed}-{offset + 1}"
        params = {"weight": seed / 10 + offset / 1000, "nested": {"i": offset}}
        first = compute_edge_hash(source, target, "adjacent", params)
        second = compute_edge_hash(source, target, "adjacent", params)
        assert first == second


# B. Directedness: reversing endpoints changes the canonical edge identity.
@pytest.mark.parametrize("index", range(20))
def test_directedness_changes_hash(index: int) -> None:
    params = {"index": index, "kind": "x"}
    forward = compute_edge_hash("u", f"v-{index}", "adjacent", params)
    reverse = compute_edge_hash(f"v-{index}", "u", "adjacent", params)
    assert forward != reverse


# C. Identity / self-loop rejection.
@pytest.mark.parametrize("index", range(20))
def test_self_loop_is_forbidden(index: int) -> None:
    node = f"atom-{index}"
    with pytest.raises(
        ValueError, match="Self-loops are forbidden in ObservationRelation"
    ):
        relation(node, node)


# D. Parameter sensitivity, including nested structures and precise floats.
@pytest.mark.parametrize(
    ("left", "right"),
    [
        ({"value": 0.1}, {"value": 0.10000000000000002}),
        ({"key": 1}, {"other_key": 1}),
        ({"nested": {"a": 1}}, {"nested": {"a": 2}}),
        ({"nested": {"a": [1, 2]}}, {"nested": {"a": [1, 3]}}),
        ({"flag": True}, {"flag": False}),
    ]
    * 5,
)
def test_parameter_change_changes_hash(left, right) -> None:
    assert compute_edge_hash("u", "v", "adjacent", left) != compute_edge_hash(
        "u", "v", "adjacent", right
    )


# E. DAG / subset validation.
@pytest.mark.parametrize("length", range(2, 22))
def test_acyclic_chain_of_length_is_valid(length: int) -> None:
    relations = tuple(relation(f"n{i}", f"n{i + 1}") for i in range(length))
    assert validate_acyclic_subset(relations) is True


@pytest.mark.parametrize("length", range(2, 12))
def test_cycle_of_length_is_rejected(length: int) -> None:
    relations = tuple(
        relation(f"n{i}", f"n{i + 1}") for i in range(length - 1)
    ) + (relation(f"n{length - 1}", "n0"),)
    assert validate_acyclic_subset(relations) is False


# F. Isolation / delta: this research module must not import JAMP core.
@pytest.mark.parametrize("module_name", ["research.exp19", "research.exp19.observation_relation"])
def test_research_module_has_no_core_imports(module_name: str) -> None:
    import importlib

    module = importlib.import_module(module_name)
    loaded = set(module.__dict__.get("__name__", "").split())
    assert not any(name == "jamp" or name.startswith("jamp.") for name in loaded)


@pytest.mark.parametrize("index", range(14))
def test_edge_hash_is_canonical_sha256(index: int) -> None:
    payload = {
        "s": f"u-{index}",
        "t": f"v-{index}",
        "r": "adjacent",
        "p": {"index": index},
    }
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    expected = hashlib.sha256(raw).hexdigest()
    assert compute_edge_hash(
        payload["s"], payload["t"], payload["r"], payload["p"]
    ) == expected


@pytest.mark.parametrize("index", range(14))
def test_relation_edge_hash_matches_function(index: int) -> None:
    rel = relation(f"u-{index}", f"v-{index}", params={"index": index})
    assert rel.edge_hash == compute_edge_hash(
        rel.source_id, rel.target_id, rel.relation_type, rel.params
    )


@pytest.mark.parametrize("index", range(14))
def test_relation_is_immutable(index: int) -> None:
    rel = relation(f"u-{index}", f"v-{index}")
    with pytest.raises((AttributeError, TypeError)):
        rel.source_id = "changed"


@pytest.mark.parametrize("index", range(14))
def test_relation_type_changes_hash(index: int) -> None:
    assert compute_edge_hash("u", "v", f"a-{index}", {}) != compute_edge_hash(
        "u", "v", f"b-{index}", {}
    )


@pytest.mark.parametrize("index", range(14))
def test_subset_validator_ignores_unrelated_external_nodes(index: int) -> None:
    subset = (
        relation(f"u-{index}", f"v-{index}"),
        relation(f"v-{index}", f"w-{index}"),
    )
    assert validate_acyclic_subset(subset) is True
