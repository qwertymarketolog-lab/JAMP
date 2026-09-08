"""Pure formal consistency checks for the JAMP EventDAG."""
from __future__ import annotations

from collections.abc import Mapping

from .event import EventNode, calculate_previous_graph_digest, calculate_state_digest, sha256_text
from .exceptions import CausalConsistencyError


class DAGConsistencyChecker:
    """Validate EventDAG invariants without mutating any supplied object."""

    GENESIS_ID = "GENESIS"
    EMPTY_GRAPH_DIGEST = sha256_text("[]")

    @classmethod
    def validate(cls, nodes: Mapping[str, EventNode]) -> None:
        """Raise CausalConsistencyError unless all P16.1 invariants hold."""
        cls._unique_ids(nodes)
        cls._genesis(nodes)
        cls._parents_exist_and_precede(nodes)
        cls._parent_order(nodes)
        cls._acyclic(nodes)
        cls._connectivity(nodes)
        cls._hash_chain(nodes)

    @staticmethod
    def _unique_ids(nodes: Mapping[str, EventNode]) -> None:
        for key, node in nodes.items():
            if key != node.event_id:
                raise CausalConsistencyError(
                    f"I1: mapping key {key!r} does not match event_id {node.event_id!r}."
                )

    @classmethod
    def _genesis(cls, nodes: Mapping[str, EventNode]) -> None:
        genesis = nodes.get(cls.GENESIS_ID)
        if genesis is None:
            raise CausalConsistencyError("I4: EventDAG must contain exactly one GENESIS node.")
        if genesis.parent_ids != ():
            raise CausalConsistencyError("I4: GENESIS must have no parents.")
        if genesis.previous_graph_digest != cls.EMPTY_GRAPH_DIGEST:
            raise CausalConsistencyError("I4/I6: GENESIS previous_graph_digest is invalid.")

    @staticmethod
    def _parents_exist_and_precede(nodes: Mapping[str, EventNode]) -> None:
        positions = {event_id: index for index, event_id in enumerate(nodes)}
        for event_id, node in nodes.items():
            if len(set(node.parent_ids)) != len(node.parent_ids):
                raise CausalConsistencyError(f"I2: {event_id} contains duplicate parents.")
            for parent_id in node.parent_ids:
                if parent_id not in nodes:
                    raise CausalConsistencyError(
                        f"I2: {event_id} references missing parent {parent_id}."
                    )
                if parent_id != "GENESIS" and positions[parent_id] >= positions[event_id]:
                    raise CausalConsistencyError(
                        f"I2: parent {parent_id} does not precede child {event_id}."
                    )

    @staticmethod
    def _parent_order(nodes: Mapping[str, EventNode]) -> None:
        for event_id, node in nodes.items():
            if node.parent_ids != tuple(sorted(node.parent_ids)):
                raise CausalConsistencyError(
                    f"I5: parent_ids for {event_id} are not canonically ordered."
                )

    @staticmethod
    def _acyclic(nodes: Mapping[str, EventNode]) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(event_id: str) -> None:
            if event_id in visiting:
                raise CausalConsistencyError(f"I3: cycle detected at {event_id}.")
            if event_id in visited:
                return
            visiting.add(event_id)
            for parent_id in nodes[event_id].parent_ids:
                visit(parent_id)
            visiting.remove(event_id)
            visited.add(event_id)

        for event_id in nodes:
            visit(event_id)

    @classmethod
    def _connectivity(cls, nodes: Mapping[str, EventNode]) -> None:
        """Require every node to be causally reachable from Genesis."""
        reachable = {cls.GENESIS_ID}
        changed = True
        while changed:
            changed = False
            for event_id, node in nodes.items():
                if event_id not in reachable and any(parent in reachable for parent in node.parent_ids):
                    reachable.add(event_id)
                    changed = True
        disconnected = set(nodes) - reachable
        if disconnected:
            raise CausalConsistencyError(
                f"I4: disconnected event nodes: {sorted(disconnected)!r}."
            )

    @classmethod
    def _hash_chain(cls, nodes: Mapping[str, EventNode]) -> None:
        for event_id, node in nodes.items():
            expected_state = calculate_state_digest(node.payload)
            if node.state_digest != expected_state:
                raise CausalConsistencyError(f"I6/I7: invalid state_digest for {event_id}.")

            if event_id == cls.GENESIS_ID:
                expected_previous = cls.EMPTY_GRAPH_DIGEST
            else:
                parents = tuple(nodes[parent_id] for parent_id in node.parent_ids)
                expected_previous = calculate_previous_graph_digest(parents)
            if node.previous_graph_digest != expected_previous:
                raise CausalConsistencyError(
                    f"I6/I7: invalid previous_graph_digest for {event_id}."
                )

            if node.digest != node.compute_digest():
                raise CausalConsistencyError(f"I7: event digest mismatch for {event_id}.")
