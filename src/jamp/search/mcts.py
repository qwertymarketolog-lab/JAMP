"""Search-domain-only Monte Carlo Tree Search policy with feedback-driven pruning."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .candidate import SearchCandidate, SearchProvenance
from .feedback import FeedbackStatus, SearchFeedback


@dataclass
class MCTSNode:
    """Mutable search-tree node; it contains no JAMP State Domain objects."""
    node_id: str
    statement: str
    parent: Optional["MCTSNode"] = None
    children: List["MCTSNode"] = field(default_factory=list)
    visits: int = 0
    value: float = 0.0
    depth: int = 0
    pruned: bool = False

    @property
    def uct_score(self) -> float:
        if self.parent is None or self.visits == 0 or self.parent.visits == 0:
            return float("inf")
        exploitation = self.value / self.visits
        exploration = math.sqrt(2.0 * math.log(self.parent.visits) / self.visits)
        return exploitation + exploration

    def update(self, reward: float) -> None:
        self.visits += 1
        self.value += reward


class MCTSPolicy:
    """Deterministic MCTS policy; feedback mutation remains inside Search Domain."""

    def __init__(
        self,
        iterations: int = 10,
        policy_name: str = "mcts_v1",
        statement_factory: Optional[Callable[[str, int], str]] = None,
    ) -> None:
        if iterations < 1:
            raise ValueError("iterations must be >= 1")
        self._iterations = iterations
        self._policy_name = policy_name
        self._statement_factory = statement_factory or (
            lambda context, index: f"Hypothesis derived from '{context}' step {index}"
        )
        self._root: Optional[MCTSNode] = None

    @property
    def name(self) -> str:
        return self._policy_name

    @property
    def root(self) -> Optional[MCTSNode]:
        return self._root

    @staticmethod
    def _select(root: MCTSNode) -> MCTSNode:
        node = root
        while node.children:
            active_children = [child for child in node.children if not child.pruned]
            if not active_children:
                node.pruned = True
                return node
            if not all(child.visits > 0 for child in active_children):
                return node
            node = max(active_children, key=lambda child: (child.uct_score, child.node_id))
        return node

    @staticmethod
    def _expand(node: MCTSNode, iteration: int, statement: str) -> MCTSNode:
        child = MCTSNode(
            node_id=f"mcts_node_{iteration}",
            statement=statement,
            parent=node,
            depth=node.depth + 1,
        )
        node.children.append(child)
        return child

    @staticmethod
    def _rollout(node: MCTSNode) -> float:
        return 0.5

    @staticmethod
    def _backpropagate(node: MCTSNode, reward: float) -> None:
        current: Optional[MCTSNode] = node
        while current is not None:
            current.update(reward)
            current = current.parent

    def _find_node(self, search_node_id: str) -> Optional[MCTSNode]:
        if self._root is None:
            return None
        stack = [self._root]
        while stack:
            node = stack.pop()
            if node.node_id == search_node_id:
                return node
            stack.extend(reversed(node.children))
        return None

    def _prune_if_exhausted(self, node: Optional[MCTSNode]) -> None:
        current = node
        while current is not None and current.children:
            if all(child.pruned for child in current.children):
                current.pruned = True
                current = current.parent
            else:
                break

    def receive_feedback(self, feedback: SearchFeedback) -> None:
        if feedback.status is not FeedbackStatus.REJECTED:
            return
        node = self._find_node(feedback.search_node_id)
        if node is None:
            return
        node.pruned = True
        self._prune_if_exhausted(node.parent)

    def propose(self, context_statement: str) -> List[SearchCandidate]:
        self._root = MCTSNode(node_id="root_0", statement=context_statement)
        proposals: List[SearchCandidate] = []
        for iteration in range(self._iterations):
            selected = self._select(self._root)
            if selected.pruned:
                break
            statement = self._statement_factory(context_statement, iteration)
            child = self._expand(selected, iteration, statement)
            reward = self._rollout(child)
            self._backpropagate(child, reward)
            proposals.append(
                SearchCandidate(
                    candidate_id=f"cand_mcts_{iteration}",
                    statement=child.statement,
                    source_id=f"mcts_source_{self.name}",
                    provenance=SearchProvenance(
                        search_node_id=child.node_id,
                        depth=child.depth,
                        score=child.uct_score,
                        policy_name=self.name,
                        metadata={
                            "visits": child.visits,
                            "value": child.value,
                            "reward": reward,
                            "iteration": iteration,
                            "pruned": child.pruned,
                        },
                    ),
                )
            )
        return proposals
