from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class Frame:
    row: int
    untried: tuple[int, ...] = (1, 2, 3, 4)
    tried: tuple[int, ...] = ()
    pruned: tuple[int, ...] = ()


@dataclass(frozen=True)
class Event:
    kind: str
    details: dict[str, Any]
    board_before: tuple[Optional[int], ...]
    board_after: tuple[Optional[int], ...]


@dataclass(frozen=True)
class QueensSearchState:
    board: tuple[Optional[int], ...] = (None, None, None, None)
    stack: tuple[Frame, ...] = (Frame(row=0),)
    solutions: tuple[tuple[int, ...], ...] = ()
    events: tuple[Event, ...] = ()
    mode: str = "EXHAUSTIVE"


class FourQueensAdapter:
    budget = 10_000

    def __init__(self, mode: str) -> None:
        if mode not in {"FIND_ONE", "EXHAUSTIVE"}:
            raise ValueError(f"unknown mode: {mode}")
        self.mode = mode

    def initial(self) -> QueensSearchState:
        return QueensSearchState(mode=self.mode)

    def _find_conflict(
        self,
        board: tuple[Optional[int], ...],
        row: int,
        col: int,
    ) -> Optional[int]:
        """Return the 1-based conflicting row, or None when safe."""
        for r in range(row):
            c = board[r]
            if c is not None and (c == col or abs(c - col) == abs(r - row)):
                return r + 1
        return None

    def candidates(self, state: QueensSearchState) -> list[str]:
        if state.mode == "FIND_ONE" and len(state.solutions) >= 1:
            return []
        if not state.stack:
            return []

        top_frame = state.stack[-1]
        if top_frame.row == 4:
            return ["SOLUTION"]

        if top_frame.untried:
            next_col = top_frame.untried[0]
            conflict_row = self._find_conflict(
                state.board, top_frame.row, next_col
            )
            if conflict_row is None:
                return [f"PLACE_{top_frame.row}_{next_col}"]
            return [
                f"PRUNE_{top_frame.row}_{next_col}_{conflict_row}"
            ]

        if len(state.stack) > 1:
            return ["BACKTRACK"]
        return []

    def admissible(self, state: QueensSearchState, candidate: str) -> bool:
        return candidate in self.candidates(state)

    def strategy(self, state: QueensSearchState, candidates: list[str]) -> str:
        return candidates[0]

    def apply(self, state: QueensSearchState, action: str) -> QueensSearchState:
        top_frame = state.stack[-1]
        row = top_frame.row
        board_before = state.board

        if action.startswith("PLACE_"):
            _, _, col_str = action.split("_")
            col = int(col_str)
            updated_top = Frame(
                row=row,
                untried=top_frame.untried[1:],
                tried=top_frame.tried + (col,),
                pruned=top_frame.pruned,
            )
            new_board = list(state.board)
            new_board[row] = col
            board_after = tuple(new_board)
            new_stack = list(state.stack[:-1]) + [updated_top]
            if row + 1 <= 4:
                new_stack.append(
                    Frame(
                        row=row + 1,
                        untried=() if row + 1 == 4 else (1, 2, 3, 4),
                    )
                )
            event = Event(
                kind="PLACE",
                details={"queen_row": row + 1, "col": col},
                board_before=board_before,
                board_after=board_after,
            )
            return QueensSearchState(
                board=board_after,
                stack=tuple(new_stack),
                solutions=state.solutions,
                events=state.events + (event,),
                mode=state.mode,
            )

        if action.startswith("PRUNE_"):
            _, _, col_str, conflict_str = action.split("_")
            col = int(col_str)
            conflict_row = int(conflict_str)
            updated_top = Frame(
                row=row,
                untried=top_frame.untried[1:],
                tried=top_frame.tried,
                pruned=top_frame.pruned + (col,),
            )
            event = Event(
                kind="PRUNE",
                details={
                    "queen_row": row + 1,
                    "col": col,
                    "conflict_with_row": conflict_row,
                },
                board_before=board_before,
                board_after=board_before,
            )
            return QueensSearchState(
                board=board_before,
                stack=state.stack[:-1] + (updated_top,),
                solutions=state.solutions,
                events=state.events + (event,),
                mode=state.mode,
            )

        if action == "SOLUTION":
            solution_vector = tuple(state.board)
            new_board = list(state.board)
            new_board[3] = None
            board_after = tuple(new_board)
            event = Event(
                kind="TERMINAL_SAT",
                details={"solution_vector": solution_vector},
                board_before=board_before,
                board_after=board_after,
            )
            return QueensSearchState(
                board=board_after,
                stack=state.stack[:-1],
                solutions=state.solutions + (solution_vector,),
                events=state.events + (event,),
                mode=state.mode,
            )

        if action == "BACKTRACK":
            popped_frame = state.stack[-1]
            parent_frame = state.stack[-2]
            new_board = list(state.board)
            new_board[parent_frame.row] = None
            board_after = tuple(new_board)
            event = Event(
                kind="BACKTRACK",
                details={
                    "from_row": popped_frame.row + 1,
                    "to_row": parent_frame.row + 1,
                },
                board_before=board_before,
                board_after=board_after,
            )
            return QueensSearchState(
                board=board_after,
                stack=state.stack[:-1],
                solutions=state.solutions,
                events=state.events + (event,),
                mode=state.mode,
            )

        raise ValueError(f"unknown action: {action}")

    def terminal(self, state: QueensSearchState) -> bool:
        if state.mode == "FIND_ONE" and len(state.solutions) >= 1:
            return True
        return len(state.stack) == 1 and len(state.stack[0].untried) == 0


__all__ = ["Event", "Frame", "FourQueensAdapter", "QueensSearchState"]
