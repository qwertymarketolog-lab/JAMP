from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from research.exp19.observation_relation import (
    ObservationRelation,
    compute_edge_hash,
    validate_acyclic_subset,
)


def _relation(
    source_id: str = "a",
    target_id: str = "b",
    relation_type: str = "supports",
    params: dict[str, object] | None = None,
) -> ObservationRelation:
    return ObservationRelation(
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
        params={} if params is None else params,
    )


@pytest.mark.parametrize("index", range(20))
def test_deterministic_edge_hash(index: int) -> None:
    params = {"weight": index, "label": f"v-{index}"}
    assert compute_edge_hash("a", "b", "supports", params) == compute_edge_hash(
        "a", "b", "supports", params
    )


@pytest.mark.parametrize("index", range(20))
def test_directed_relation_changes_with_reversed_endpoints(index: int) -> None:
    assert _relation(f"a-{index}", f"b-{index}").edge_hash != _relation(
        f"b-{index}", f"a-{index}"
    ).edge_hash


@pytest.mark.parametrize("index", range(20))
def test_self_loop_is_forbidden(index: int) -> None:
    with pytest.raises(
        ValueError,
        match="Self-loops are forbidden in ObservationRelation",
    ):
        _relation(f"node-{index}", f"node-{index}")


@pytest.mark.parametrize("index", range(25))
def test_params_change_edge_identity(index: int) -> None:
    left = _relation(params={"k": index})
    right = _relation(params={"k": index + 1})
    assert left.edge_hash != right.edge_hash


@pytest.mark.parametrize("index", range(20))
def test_acyclic_dag_is_accepted(index: int) -> None:
    relations = (
        _relation(f"a-{index}", f"b-{index}"),
        _relation(f"b-{index}", f"c-{index}"),
        _relation(f"a-{index}", f"c-{index}"),
    )
    assert validate_acyclic_subset(relations)


@pytest.mark.parametrize("index", range(20))
def test_cyclic_subset_is_rejected(index: int) -> None:
    relations = (
        _relation(f"a-{index}", f"b-{index}"),
        _relation(f"b-{index}", f"c-{index}"),
        _relation(f"c-{index}", f"a-{index}"),
    )
    assert not validate_acyclic_subset(relations)


@pytest.mark.parametrize("index", range(14))
def test_edge_hash_is_canonical_sha256(index: int) -> None:
    params = {"index": index, "unicode": "ё"}
    payload = {
        "s": f"a-{index}",
        "t": f"b-{index}",
        "r": "supports",
        "p": params,
    }
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    assert compute_edge_hash(
        payload["s"],
        payload["t"],
        payload["r"],
        payload["p"],
    ) == expected


def test_mapping_order_does_not_change_hash() -> None:
    assert compute_edge_hash("a", "b", "r", {"x": 1, "y": 2}) == compute_edge_hash(
        "a", "b", "r", {"y": 2, "x": 1}
    )


def test_empty_subset_is_acyclic() -> None:
    assert validate_acyclic_subset(())


def test_isolation_source_has_no_jamp_imports() -> None:
    source = Path("research/exp19/observation_relation.py").read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        assert all(name != "jamp" and not name.startswith("jamp.") for name in names)


@pytest.mark.parametrize(
    "path",
    [
        "research/exp19/observation_relation.py",
        "tests/research/exp19/test_observation_relation.py",
    ],
)
def test_exp19_paths_are_outside_core(path: str) -> None:
    resolved = Path(path).resolve()
    core = Path("src/jamp").resolve()
    assert core not in resolved.parents
