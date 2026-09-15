from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Node:
    id: int
    name: str


X = Node(0, "X")
A = Node(1, "A")
B = Node(2, "B")
S = Node(3, "S")
G = Node(4, "G")

EDGES: dict[int, tuple[int, ...]] = {
    S.id: (A.id, B.id),
    A.id: (X.id,),
    X.id: (),
    B.id: (G.id,),
    G.id: (),
}

NODES: dict[int, Node] = {node.id: node for node in (X, A, B, S, G)}


def successors(node_id: int) -> tuple[int, ...]:
    return EDGES[node_id]
