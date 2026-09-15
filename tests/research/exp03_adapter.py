from __future__ import annotations

from dataclasses import dataclass

from exp03_graph import G, S, successors


@dataclass(frozen=True)
class SearchState:
    current: int
    frontier: tuple[int, ...]
    visited: tuple[int, ...]


class Exp03Adapter:
    budget = 10

    def __init__(self) -> None:
        self.history: list[tuple[SearchState, int, SearchState]] = []

    def initial(self) -> SearchState:
        return SearchState(current=S.id, frontier=(S.id,), visited=())

    def candidates(self, state: SearchState) -> tuple[int, ...]:
        return state.frontier

    def admissible(self, state: SearchState, candidate: int) -> bool:
        return candidate in state.frontier and candidate not in state.visited

    def strategy(self, state: SearchState, cands: tuple[int, ...]) -> int:
        return min(cands)

    def apply(self, state: SearchState, candidate: int) -> SearchState:
        if not self.admissible(state, candidate):
            raise ValueError(f"inadmissible candidate: {candidate}")

        frontier = [node_id for node_id in state.frontier if node_id != candidate]
        visited = state.visited + (candidate,)

        for successor in successors(candidate):
            if successor not in visited and successor not in frontier:
                frontier.append(successor)

        new_state = SearchState(
            current=candidate,
            frontier=tuple(frontier),
            visited=visited,
        )
        self.history.append((state, candidate, new_state))
        return new_state

    def terminal(self, state: SearchState) -> bool:
        return G.id in state.visited


__all__ = ["SearchState", "Exp03Adapter"]
