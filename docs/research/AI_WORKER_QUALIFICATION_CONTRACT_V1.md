# AI Worker Qualification Contract v1

Status: CONTRACT
Version: v1
Scope: AnyModel models evaluated by committed R01-R30 evidence
Frozen Core: `src/jamp/run.py` remains locked; qualification MUST NOT modify it.

## 1. Decision classes

- `QUALIFIED`: all mandatory P0 gates are VERIFIED, none are CONTRADICTED, and provenance/identity evidence is VERIFIED.
- `CANDIDATE`: current derived evidence is sufficient for further qualification work, but the full qualification contract is not yet satisfied.
- `INCONCLUSIVE`: required evidence is missing, non-terminal, conflicting, or explicitly classified INCONCLUSIVE.
- `NOT_QUALIFIED`: at least one mandatory P0 condition is CONTRADICTED or the model fails the applicable qualification contract.

These are evidence states, not rankings.

## 2. R01-R30 evidence contract

R01-R30 are the evidence surface. Each result MUST preserve its raw observation and derived classification.

Priority currently encoded by the committed audit:
- P0: R01-R07, R09, R11, R18-R24, R27, R30
- P1: R08, R10, R12-R17, R25-R26
- P2: R28-R29

Where a test's semantic definition is not explicitly present in this contract, the source R01-R30 artifact is authoritative; this contract does not invent a meaning.

## 3. Mandatory qualification gates

A model can become `QUALIFIED` only if:

1. Every applicable P0 result is `VERIFIED`.
2. No applicable P0 result is `CONTRADICTED`.
3. R27 provenance/identity evidence is `VERIFIED`.
4. The evidence binds the result to the exact provider/model identifier and evaluation artifact.
5. The evidence is reproducible from committed artifacts or a newly recorded terminal run.
6. No unresolved conflict exists between raw evidence and its derived classification.
7. Frozen Core integrity is preserved.

P1/P2 evidence is capability evidence. `INCONCLUSIVE` P1/P2 does not by itself produce `QUALIFIED`, but it MUST be recorded as an explicit limitation. A `CONTRADICTED` P1/P2 result MUST remain visible and MUST NOT be rewritten as PASS.

## 4. Fail-closed rules

- Missing evidence != VERIFIED.
- HTTP/API failure != model capability evidence.
- HTTP 402/non-success response is INCONCLUSIVE unless a separate contract explicitly proves another classification.
- Empty CI jobs != PASS.
- PR CI != post-merge CI.
- Code inspection != runtime verification.
- Historical evidence != current evidence.
- No synthetic PASS.
- Conflicts remain conflicts until resolved by new evidence.

## 5. Qualification output

Every qualification record MUST contain:
- exact model/provider ID;
- contract version;
- R01-R30 evidence references;
- raw artifact references and hashes where available;
- derived status;
- unresolved limitations/conflicts;
- source commit SHA;
- CI/run evidence for generated artifacts;
- Frozen Core integrity evidence.

## 6. Requalification

A model MUST be re-evaluated when:
- provider/model identity changes;
- endpoint/protocol changes materially;
- the R01-R30 contract changes;
- new contradictory evidence appears;
- provenance becomes stale or unverifiable.

Requalification creates new evidence. Existing raw artifacts are immutable.

## 7. Current interpretation

The existing 87-model crosswalk uses `CANDIDATE`, `INCONCLUSIVE`, and `NOT_QUALIFIED`. It does NOT claim that the 25 CANDIDATE models are already QUALIFIED AI workers.

Under this v1 contract, qualification is a separate evidence gate. Current candidates require additional proof where mandatory P0 or provenance evidence is not yet VERIFIED.
