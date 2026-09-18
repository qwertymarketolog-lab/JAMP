"""EXP-28: real unresolved Millennium Problem input through the JAMP execution boundary.

Research-only harness.  No solver or production/runtime changes are introduced.
The experiment records a finite numerical observation about the Riemann
Hypothesis; it does not claim to prove the hypothesis.
"""

from __future__ import annotations

from jamp.research.execution import make_execution

QUESTION_HASH = "80b978e61655aebf83d2ee50d56dfd870847faf14846992edd5fc9521c01f0d1"
PLAN_HASH = "d5f2d66dc38e1f7a0904c987e5d6827ca965e9edcf2e775d8fdb0c14161319dd"

# Independently computed finite observations of the first five non-trivial
# zeros of zeta(s), recorded at 30 decimal digits.  The numerical method used
# for acquisition was mpmath.zetazero(n); the values are stored here so CI does
# not depend on the external numerical package.
OBSERVATIONS = [
    {
        "zero_index": 1,
        "real_part": 0.5,
        "imag_part": 14.1347251417346937904572519835617,
        "metadata": {"acquisition_method": "mpmath.zetazero", "precision_dps": 30},
    },
    {
        "zero_index": 2,
        "real_part": 0.5,
        "imag_part": 21.0220396387715549926284795938965,
        "metadata": {"acquisition_method": "mpmath.zetazero", "precision_dps": 30},
    },
    {
        "zero_index": 3,
        "real_part": 0.5,
        "imag_part": 25.010857580145688763213790992564,
        "metadata": {"acquisition_method": "mpmath.zetazero", "precision_dps": 30},
    },
    {
        "zero_index": 4,
        "real_part": 0.5,
        "imag_part": 30.4248761258595132103118975305851,
        "metadata": {"acquisition_method": "mpmath.zetazero", "precision_dps": 30},
    },
    {
        "zero_index": 5,
        "real_part": 0.5,
        "imag_part": 32.9350615877391896906623689640763,
        "metadata": {"acquisition_method": "mpmath.zetazero", "precision_dps": 30},
    },
]


def test_exp28_real_millennium_input_is_captured_and_verified() -> None:
    execution = make_execution(
        plan_hash=PLAN_HASH,
        question_hash=QUESTION_HASH,
        parameters={
            "task": "Riemann Hypothesis",
            "question": (
                "Do the first five non-trivial zeros of the Riemann zeta "
                "function have real part 1/2?"
            ),
            "scope": {"zero_indices": [1, 2, 3, 4, 5]},
            "criterion": "finite_observation_real_part_equals_0.5",
            "acquisition": {
                "method": "mpmath.zetazero",
                "precision_dps": 30,
            },
        },
        observations=OBSERVATIONS,
    )

    assert execution.verify() is True
    assert execution.observation_status == "CAPTURED"
    assert len(execution.observations) == 5
    assert all(obs["real_part"] == 0.5 for obs in execution.observations)
    assert [obs["zero_index"] for obs in execution.observations] == [1, 2, 3, 4, 5]


def test_exp28_does_not_turn_finite_observation_into_a_theorem() -> None:
    execution = make_execution(
        plan_hash=PLAN_HASH,
        question_hash=QUESTION_HASH,
        parameters={
            "task": "Riemann Hypothesis",
            "question": (
                "Do the first five non-trivial zeros of the Riemann zeta "
                "function have real part 1/2?"
            ),
            "scope": {"zero_indices": [1, 2, 3, 4, 5]},
            "criterion": "finite_observation_real_part_equals_0.5",
        },
        observations=OBSERVATIONS,
    )

    exported = execution.export()

    assert exported["observation_status"] == "CAPTURED"
    assert all(
        "claim" not in obs and "interpretation" not in obs for obs in exported["observations"]
    )
