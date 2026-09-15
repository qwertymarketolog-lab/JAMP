# Track A adapter equivalence result

Gate:          `tests/research/test_track_a_equivalence.py`
Cases:         15 (roots `{2,3,5}` × seeds `{0,1,2,42,99}`)
Anchor:        `track_a/common.py @ 4b8aa64` (direct run)
Adapter:       `tests/research/track_a_run_adapter.py` (D1–D8)

## Observed PASS

Observed PASS on: `5155bc3c547530db53380ef06d677ae7a18e206a`

This was the SHA at the actual execution of the equivalence test. It is a pre-cosmetic state relative to the later rename-only change; execution provenance is kept separate from the later commit state.

Verified (15/15):

- final object set equality (order-independent)
- stop reason mapping `MAX_ITERATIONS → budget`
- `iterations == 500`
- `steps == 4`
- `final_size == 13`

## Post-cosmetic state

`3fb8852a` is a rename-only change. The equivalence execution was not repeated after that cosmetic change because no execution channel was available.

## Not compared

- `Track A.steps` (`len(history)`, 13) vs `RunResult.steps` (4) — documented D8 divergence.

The equivalence gate therefore establishes the listed object-set, stop-mapping, iteration, step, and final-size checks only; it does not establish equality of the two step-count semantics.
