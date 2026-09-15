# Track A adapter equivalence result

## Gate

- File:    `tests/research/test_track_a_equivalence.py`
- History: introduced in `2def08a`, label-corrected in `3fb8852`
- Adapter: `tests/research/track_a_run_adapter.py` (D1–D8)
- Anchor:  `track_a/common.py @ 4b8aa64e` (direct run, reference semantics)

## Observed result

PASS 15/15 during pre-cosmetic development of the gate file.

- Cases:   15 (roots {2,3,5} × seeds {0,1,2,42,99})
- Verified (all 15/15):
    * final object set equality (order-independent)
    * stop reason mapping MAX_ITERATIONS → budget
    * iterations == 500
    * steps == 4
    * final_size == 13
- Not compared:
    * Track A.steps (len(history), 13) vs RunResult.steps (4)
      — documented D8 divergence

## Provenance note

Exact commit SHA on which the 15/15 PASS was executed is **not recorded**.
The run was performed on a local working tree during development of the
gate file; no automatic attribution to a commit exists.

`3fb8852` changes only label text within the gate file
(`30 cases` → `15 cases`, `test_equivalence_30` → `test_equivalence_15`,
`30/30 PASS` → `15/15 PASS`). It is a label-only correction and does not
constitute a re-execution of the gate.

Therefore:

- The equivalence result is a real observation.
- Its SHA attribution is unknown.
- `3fb8852` is not the execution commit; it is the label-corrected
  version of the same file whose pre-correction state was observed to
  PASS 15/15.

No claim is made here about which commit the PASS ran against.

## Anchored execution — 2026-09-15

Fresh execution against commit `ac166a55872adf697e9c03618a32e8c2d652423f`.

Command: `PYTHONPATH=src python -m pytest -q tests/research/test_track_a_equivalence.py`

Result: **1 passed in 28.08s — 15/15 equivalence cases PASS.**

Environment: Python 3.14.6, Termux/Android, `PYTHONPATH=src`.

At execution time `HEAD` and `origin/o4-tighten-v01` were both `ac166a55872adf697e9c03618a32e8c2d652423f`; working tree was clean.

This fresh execution closes the previous provenance gap: the earlier 15/15 observation did not record its exact execution SHA.
