"""Equivalence gate: adapter vs direct Track A semantics on 30 cases."""
from __future__ import annotations

import random

from track_a.common import State, run as track_a_run, target_substitution

from tests.research.track_a_run_adapter import run_track_a_via_adapter


ROOTS = [2, 3, 5]
SEEDS = [0, 1, 2, 42, 99]
N = 500
MAX_OBJECTS = 120


def canon_objects(state):
    """Order-independent representation of state.objects."""
    return sorted(repr(o) for o in state.objects)


def direct_state(root, seed, N, max_objects=120):
    """Replay current TREATMENT_TARGETED Track A semantics and return State."""
    rng = random.Random(seed)
    state = State(root, max_objects)
    state.closure()
    for _ in range(N):
        if state.solved:
            break
        out = target_substitution(state, rng)
        rng.shuffle(out)
        sub = out[:1]
        if not sub:
            state.closure()
            continue
        state.add(sub[0].new, sub[0].op, sub[0].parents)
        state.closure()
    return state


def test_equivalence_30():
    for root in ROOTS:
        for seed in SEEDS:
            direct_result = track_a_run(
                seed, root, "TREATMENT_TARGETED", N, MAX_OBJECTS
            )
            direct = direct_state(root, seed, N, MAX_OBJECTS)
            adapter = run_track_a_via_adapter(root, seed, N, MAX_OBJECTS)

            assert direct_result["stop_reason"] == "MAX_ITERATIONS", (
                f"direct stop root={root} seed={seed}: "
                f"{direct_result['stop_reason']}"
            )
            assert canon_objects(direct) == canon_objects(adapter.state), (
                f"state mismatch root={root} seed={seed}"
            )
            assert adapter.stop_reason.kind == "budget", (
                f"adapter stop root={root} seed={seed}: {adapter.stop_reason}"
            )
            assert adapter.iterations == N, (
                f"iterations root={root} seed={seed}: {adapter.iterations}"
            )
            assert adapter.steps == 4, (
                f"steps root={root} seed={seed}: {adapter.steps}"
            )
            assert len(adapter.state.objects) == 13, (
                f"final_size root={root} seed={seed}: {len(adapter.state.objects)}"
            )

    print("track_a equivalence: 30/30 PASS")


if __name__ == "__main__":
    test_equivalence_30()
