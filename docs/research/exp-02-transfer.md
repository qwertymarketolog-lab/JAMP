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

## Result

### Core level — PASS

The existing Run v0.3 Core executed the 8-puzzle adapter without
modification.

Observed result:

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

The 8-puzzle adapter records two non-empty transitions:

```text
state_before --RIGHT--> state_after
state_before --RIGHT--> state_after
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

A minimal neutral JSON representation was produced for the 8-puzzle
without changing the production exporter or the Core.

The neutral representation contains:

```text
contract
adapter
run_result
final_state
provenance
```

For 8-puzzle:

```json
"final_state": [1,2,3,4,5,6,7,8,0]
```

and provenance contains state/action/state transitions.

Track A already has a working artifact representation through the
existing exporter, which remains unchanged.

Therefore a neutral artifact representation has been demonstrated for
two structurally different domains.

This does **not** establish general artifact neutrality.

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

## Experimental boundary

EXP-02 ends here.

No production exporter redesign, third-domain experiment, generic
artifact API, or universal-domain architecture is introduced by this
experiment.

Any such work requires a separate experimental decision.
