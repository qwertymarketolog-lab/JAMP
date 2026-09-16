# EXP-08 — Methodological Gap Note

**Status:** FINAL AUDIT NOTE
**Experiment:** EXP-08 — Mutation Resistance, v1
**Purpose:** Preserve the methodological result of the v1 audit without modifying the frozen specification, raw execution evidence, classification, or evidence index.

## 1. Provenance & Baseline

The EXP-08 v1 specification was frozen before execution.

- Specification: `docs/research/EXP-08-SPEC.md`
- Frozen specification blob SHA-1: `c505ffd1ca0a2e7071313c95b6d8a75b19ac5641`
- Baseline commit recorded by the specification: `e241872ab3ed12d09a050e46c6259082e745ab0e`
- Execution CI run: `35061282830`
- Execution commit recorded in the raw execution document: `171bbbaada6285f6f2cae33c8dc8eb3494ab8317`
- Raw artifact: `exp-08-raw-observations`
- Raw artifact SHA-256: `eb3a7d23c7c877e1ef9cca8ad82090a4dc426adc641b0fed272b3394a1df349`

A historical audit checked the pre-execution chain and confirmed that the same frozen specification blob was already present before the mutation execution commits. The checked history therefore does not provide evidence of a later insertion of mutation-specific verdict criteria into the frozen v1 specification.

## 2. Empirical Result

The raw execution produced 12 observations across mutation classes M1–M6. A separate classification document records:

- **A — Observable Difference:** 8
- **B — Structural Rejection:** 2
- **C — Silent Acceptance:** 2
- **D — Unexpected Failure:** 0

Classification is preserved as an empirical description of the observed replay behavior. It is not converted here into a retrospective score.

## 3. Methodological Gap

The frozen v1 specification requires predefined mutation-specific verdict criteria, but it does not contain concrete rules mapping individual mutations or reaction classes to `PASS`, `FAIL`, or `INCONCLUSIVE`.

The relevant frozen sections leave the per-mutation verdicts as `TBD` and state that final verdicts must follow predefined mutation-specific criteria. The historical audit found no earlier checked version of the frozen specification containing those missing criteria.

Consequently, a numerical Mutation Score cannot be derived from EXP-08 v1 without introducing a rule after observing the results. Such a rule would be retrospective and would violate the pre-execution separation between protocol and outcome.

## 4. Status Boundary

The correct v1 status is therefore:

- **Raw execution:** complete and evidenced.
- **Empirical classification:** complete (`A=8, B=2, C=2, D=0`).
- **Mutation Score:** `PENDING`.
- **Overall Verdict:** `PENDING`.

`PENDING` here records a specification-level measurement limitation. It does not reclassify the raw experiment as a failed execution.

A changed DAG hash is not, by itself, treated as protective detection. Likewise, structural rejection under the predefined replay surface is distinct from a demonstrated ability to detect arbitrary mutations. These boundaries remain those of the v1 protocol and classification.

## 5. Anti-Retrospective Rule

No PASS/FAIL mapping, Mutation Score, or overall experimental verdict will be assigned retrospectively to EXP-08 v1 on the basis of the observed outcomes.

In particular, this note does **not** modify the frozen specification to add missing criteria after execution.

## 6. Preservation Boundary

This audit note intentionally leaves the following historical artifacts unchanged:

1. `docs/research/EXP-08-SPEC.md`
2. `docs/research/EXP-08-EXECUTION.md`
3. the raw CI artifact and its recorded SHA-256
4. `docs/research/EXP-08-CLASSIFICATION.md`
5. `docs/research/evidence-index.md` or equivalent evidence-index state

The resulting provenance chain is:

**FROZEN SPEC v1 → RAW EXECUTION → CLASSIFICATION → METHODOLOGICAL GAP → future SPEC v2**

## 7. Future Work Boundary

If a numerical Mutation Score or formal PASS/FAIL/INCONCLUSIVE verdict is required, the criteria must be specified in a new, explicitly identified EXP-08 specification revision before a new independent execution cycle.

That future revision must not retroactively score EXP-08 v1.

**Conclusion:** EXP-08 v1 is retained as an executed and classified historical experiment whose methodological gap is itself an auditable result. The unresolved score and verdict remain `PENDING` by design of the audit boundary, not by retrospective inference.
