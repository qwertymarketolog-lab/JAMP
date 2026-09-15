# EXP-02: transfer of Run/Artifact to second domain (8-puzzle)

**Status:** snapshot as of 2026-09-15  
**Result:** PARTIAL TRANSFER

## Question

Which parts of the existing JAMP contract transfer to a second
state-space domain without semantic change?

## Method

- **Domain:** 8-puzzle (discrete state-space / combinatorial domain)
- **Core:** `src/jamp/run.py` — unchanged
- **Adapter:** `tests/research/puzzle8_run_adapter.py`
- **Transfer tests:** `tests/research/test_puzzle8_transfer.py`
  and `tests/research/test_puzzle8_provenance.py`
- **Neutral artifact experiment:** `tests/research/neutral_export.py`
- **Production exporter:** `scripts/export_run_result.py` — unchanged

The experiment deliberately separates Core transfer from artifact
production. The existing Track-A exporter was not modified.

## Result (executed at `0fcc8dfe42f8f120926e24d3d2f96d068b3e5c74`)

Working tree: clean at execution time.

### Core transfer — PASS

The existing Run v0.3 Core executed the 8-puzzle adapter without
modification.

Command:

```text
PYTHONPATH=src:. python -m pytest -q \
  tests/research/test_puzzle8_transfer.py \
  tests/research/test_puzzle8_provenance.py
```

Result:

```text
2 passed in 0.49s
```

The same execution produced:

```text
steps=2
iterations=2
stop_reason=terminal

START:
(1,2,3,4,5,6,0,7,8)

GOAL:
(1,2,3,4,5,6,7,8,0)
```

The goal was reached through two `RIGHT` actions.

No change was made to `src/jamp/run.py`.

### Adapter provenance — PASS

The same SHA-anchored execution recorded two non-empty transitions:

```text
START
  --RIGHT-->
(1,2,3,4,5,6,7,0,8)
  --RIGHT-->
(1,2,3,4,5,6,7,8,0)
```

Track A provenance has a different structure:

```text
step / op / parents / expr
```

8-puzzle provenance has:

```text
state_before / action / state_after
```

This demonstrates that the Core can accommodate structurally different
provenance forms.

It does **not** establish semantic equivalence between the two
provenance models.

### Artifact-exists — PASS (two domains)

The neutral exporter executed at the same commit produced:

```text
contract:     run-v0.3
adapter:      8puzzle
steps:        2
iterations:   2
stop_reason:  terminal
final_state:  [1,2,3,4,5,6,7,8,0]
provenance:   two RIGHT transitions START -> intermediate -> GOAL
```

The neutral representation contains Run-level result fields together
with domain payload without requiring Track-A-specific internal
structure.

The execution above is anchored to the exact repository commit shown
in this section. The working tree was clean, so the result does not
depend on uncommitted local copies of the experiment files.

### Artifact-production-transfer — NOT TESTED

The production exporter:

```text
scripts/export_run_result.py
```

remains intentionally Track-A-specific.

It depends on Track-A concepts including:

```text
track_a_run_adapter
D1-D8
root
seed
N
max_objects
track_a_history_len
state.objects
```

It was deliberately not rewritten.

Production exporter generalization is Q3b and is outside EXP-02.

### Third-domain neutrality — NOT TESTED

Two domains passing does not establish general neutrality.

The experiment does not establish that:

- every possible state representation is supported;
- every possible provenance representation is supported;
- provenance semantics are shared between domains;
- a third domain will not require additional fields;
- the neutral schema is minimal or canonical.

## What this establishes

1. The Core abstraction is not demonstrated to be Track-A-specific.
2. Run v0.3 executes a second, structurally different domain without
   changing `src/jamp/run.py`.
3. A neutral JSON artifact representation exists for at least two
   domains.
4. State and provenance can differ structurally while remaining
   JSON-representable.
5. The existing production exporter is a Track-A-specific instantiation
   and must not be conflated with the neutral representation.

## What this does not establish

- FULL TRANSFER;
- production exporter transfer (Q3b);
- general artifact neutrality beyond two domains;
- semantic equivalence of provenance;
- a minimal or canonical neutral schema;
- a universal domain-agnostic JAMP search system.

## Transfer classification

```text
Core transfer:                    PASS
Artifact-exists:                  PASS (two domains)
Artifact-production-transfer:     NOT TESTED
Third-domain neutrality:          NOT TESTED

Overall:                           PARTIAL TRANSFER
```

`PARTIAL TRANSFER` is not a failure state.

It records positive experimental results while preserving the questions
that have not yet been tested.

## Git controls

The experiment was checked to ensure that:

```text
git diff --stat src/jamp/run.py scripts/export_run_result.py
```

is empty.

`git diff --check` was clean.

No changes were made to the Core or the existing production exporter.

The SHA-anchored execution recorded above was performed after checking
out the exact implementation commit `0fcc8dfe42f8f120926e24d3d2f96d068b3e5c74`
with a clean working tree.

## Experimental boundary

EXP-02 ends here.

No production exporter redesign, third-domain experiment, generic
artifact API, or universal-domain architecture is introduced by this
experiment.

Any such work requires a separate experimental decision.
