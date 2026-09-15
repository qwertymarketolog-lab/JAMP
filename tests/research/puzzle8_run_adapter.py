from __future__ import annotations

from jamp.run import run

State = tuple[int, ...]
Action = str

GOAL: State = (1, 2, 3, 4, 5, 6, 7, 8, 0)
START: State = (1, 2, 3, 4, 5, 6, 0, 7, 8)


class Puzzle8Adapter:
    def __init__(self, budget: int = 10):
        self.budget = budget
        self.history: list[tuple[State, Action, State]] = []

    def initial(self) -> State:
        return START

    def candidates(self, state: State) -> tuple[Action, ...]:
        return ("UP", "DOWN", "LEFT", "RIGHT")

    def admissible(self, state: State, action: Action) -> bool:
        blank = state.index(0)
        row, col = divmod(blank, 3)
        return {
            "UP": row > 0,
            "DOWN": row < 2,
            "LEFT": col > 0,
            "RIGHT": col < 2,
        }[action]

    def apply(self, state: State, action: Action) -> State:
        blank = state.index(0)
        row, col = divmod(blank, 3)
        target = {
            "UP": (row - 1, col),
            "DOWN": (row + 1, col),
            "LEFT": (row, col - 1),
            "RIGHT": (row, col + 1),
        }[action]
        target_index = target[0] * 3 + target[1]
        board = list(state)
        board[blank], board[target_index] = board[target_index], board[blank]
        new_state = tuple(board)
        self.history.append((state, action, new_state))
        return new_state

    def terminal(self, state: State) -> bool:
        return state == GOAL

    def strategy(self, state: State, cands: tuple[Action, ...]) -> Action:
        if state == START:
            return "RIGHT"
        if state == (1, 2, 3, 4, 5, 6, 7, 0, 8):
            return "RIGHT"
        return next(iter(cands))


def run_puzzle8_via_core(budget: int = 10):
    return run(Puzzle8Adapter(budget))
