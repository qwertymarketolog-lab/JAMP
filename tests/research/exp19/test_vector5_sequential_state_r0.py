"""Vector #5: sequential-state / dispatch-order probe.

Research-only test. Frozen core is intentionally untouched.
"""

import dataclasses
import random


N = 40
SEED = 1905
TAIL_POSITIONS = {2, 15, 22, 35}


@dataclasses.dataclass(frozen=True)
class DispatchRecord:
    dispatch_position: int
    iteration_id: int


def deterministic_permutation(n: int = N, seed: int = SEED) -> list[int]:
    values = list(range(n))
    random.Random(seed).shuffle(values)
    return values


def make_dispatch(sequence: list[int]) -> list[DispatchRecord]:
    return [
        DispatchRecord(dispatch_position=pos, iteration_id=iteration_id)
        for pos, iteration_id in enumerate(sequence)
    ]


def test_vector5_permutation_is_deterministic_and_preserves_domain() -> None:
    shuffled = deterministic_permutation()
    assert shuffled == deterministic_permutation()
    assert len(shuffled) == N
    assert sorted(shuffled) == list(range(N))
    assert shuffled != list(range(N))


def test_vector5_dispatch_mapping_is_explicit() -> None:
    baseline = make_dispatch(list(range(N)))
    shuffled = make_dispatch(deterministic_permutation())

    assert [r.dispatch_position for r in baseline] == list(range(N))
    assert [r.dispatch_position for r in shuffled] == list(range(N))
    assert {r.iteration_id for r in baseline} == set(range(N))
    assert {r.iteration_id for r in shuffled} == set(range(N))


def test_vector5_tail_positions_are_treated_as_observations_not_causes() -> None:
    # This is deliberately a contract-level guard: the known tail positions
    # are inputs to analysis, never an assertion about their causal origin.
    assert {2, 15, 22, 35} == TAIL_POSITIONS
    assert TAIL_POSITIONS.issubset(set(range(N)))


def test_vector5_r0_contract() -> None:
    assert N == 40
    assert SEED == 1905
    assert {2, 15, 22, 35} == TAIL_POSITIONS
