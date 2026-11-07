# EXP-C-HD-01 — Independent C-HD Evidence Reproduction

Status: EXECUTION / awaiting terminal CI evidence

## Purpose

Independently reproduce the formal-verification portion of the C-HD shortest-path result reported by Vals AI, then keep the formal theorem claim separate from any empirical performance claim.

## External evidence snapshot

- Repository: `spicylemonade/c-hd-proof`
- Frozen repository commit: `98c53accb47a505482a1781597ae14bf67e81cec`
- Lean: `leanprover/lean4:v4.34.0`
- Mathlib: `5ed2965256430c3649e86755f9576b54eca72435`
- Final theorem names: `Frontier.CHD.Final.chd_exact_within`, `chd_CHDTarget`, `chd_gateC`
- Formal density condition: `m <= n * floor(floor(log2 n)^(3/4))`
- Stated asymptotic profile: `O(n log(n)^(11/12)))
- Reported kernel replay: 18,994 project constants
- Reported full build: 2,548 jobs

These are external claims until the JAMP workflow produces terminal evidence.

## Verification sequence

1. Bind the external source to the exact C-HD commit SHA.
2. Verify the JAMP PR head SHA and Frozen Core blob before research execution.
3. Run the publisher's frozen `formal/check.sh` without modification.
4. Capture stdout/stderr as an immutable CI artifact.
5. Require the expected theorem/axiom/replay evidence from the publisher's checker.
6. Do not infer practical speedup from formal proof success.
7. Only after formal reproduction succeeds, add a separate independent correctness/performance harness.

## Exit semantics

- `VERIFIED`: a specific claim has terminal, reproducible evidence.
- `INCONCLUSIVE`: required evidence is missing, fails, or cannot be independently reproduced.
- No overall "C-HD is faster in practice" verdict is permitted from this phase.

## JAMP invariants

- `src/jamp/run.py` is not modified.
- Frozen Core blob remains `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.
- No G4 threshold changes.
- No test/assertion/scientific criterion weakening.
- Research-only changes.
