"""Track A adapter to Run contract v0.3. Implements D1–D8.

Used only for the equivalence gate. Track A itself is unchanged.
Production run() at track_a/common.py remains the verification anchor.
"""
from __future__ import annotations

import random

from jamp.run import run

from track_a.common import State, target_substitution


class TrackAAdapter:
    """D1–D8 adapter. See docs/run/track-a-adapter-contract.md."""

    def __init__(self, root: int, seed: int, N: int, max_objects: int = 120):
        self.root = root
        self.seed = seed
        self.N = N
        self.max_objects = max_objects
        self.budget = N
        self.rng = random.Random(seed)

    def initial(self) -> State:
        s = State(self.root, self.max_objects)
        s.closure()
        return s

    def candidates(self, state: State):
        return target_substitution(state, self.rng)

    def admissible(self, state: State, c) -> bool:
        return True

    def apply(self, state: State, c) -> State:
        state.add(c.new, c.op, c.parents)
        state.closure()
        return state

    def on_empty(self, state: State) -> State:
        state.closure()
        return state

    def terminal(self, state: State) -> bool:
        return state.solved

    def strategy(self, state: State, cands):
        lst = list(cands)
        self.rng.shuffle(lst)
        return lst[0]


def run_track_a_via_adapter(root, seed, N, max_objects=120):
    adapter = TrackAAdapter(root, seed, N, max_objects)
    return run(adapter)
