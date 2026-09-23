"""P2-C negative cases for lineage identity and integrity boundaries.

Research-only coverage. NC-4 remains an explicit contract gap because the
current lineage_graph API has no canonical-root/orphan-fragment contract.
"""

from __future__ import annotations

import pytest

from jamp.research.lineage_graph import (
    LineageNode,
    build_lineage_graph,
    verify_lineage,
)


def test_nc1_missing_parent_is_rejected() -> None:
    child = LineageNode("a" * 64, ("b" * 64,))
    with pytest.raises(ValueError, match="missing parent"):
        build_lineage_graph((child,))


def test_nc2_tampered_node_is_rejected() -> None:
    root = LineageNode("a" * 64, ())
    graph = build_lineage_graph((root,))
    object.__setattr__(root, "node_hash", "f" * 64)
    with pytest.raises(ValueError):
        verify_lineage(graph)


def test_nc3_duplicate_identity_is_rejected() -> None:
    node = LineageNode("a" * 64, ())
    conflicting = LineageNode("a" * 64, ("b" * 64,))
    with pytest.raises(ValueError, match="duplicate node identity"):
        build_lineage_graph((node, conflicting))


def test_nc4_orphaned_fragment_is_explicit_contract_gap() -> None:
    """NC-4 cannot be asserted until canonical-root semantics exist."""
    root = LineageNode("a" * 64, ())
    orphan = LineageNode("b" * 64, ())
    graph = build_lineage_graph((root, orphan))

    # The present API treats both nodes as valid roots. There is no canonical
    # root parameter or reachability contract against which to reject `orphan`.
    assert verify_lineage(graph) is True
    pytest.skip("NC-4 contract gap: canonical-root/orphan semantics are undefined")
