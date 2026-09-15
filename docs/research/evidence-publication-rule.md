# Evidence publication rule

## Canonical publication rule

JAMP uses **any-ref-with-index** for research evidence chains.

A closed experiment is canonically published when its evidence chain is reachable from the repository default branch (`main`) through an explicit reference in `docs/research/evidence-index.md` to the exact branch/ref and repository paths containing the evidence.

The evidence itself may remain on a dedicated branch. An auditor must not infer publication merely from the existence of an arbitrary branch.

This rule is the criterion for the retroactive publication audit of EXP-02, Q3b, and EXP-03.

## Audit rule

For reconstruction audits, the auditor reads only evidence reachable through the canonical index and the exact referenced refs/files. `main-only` is not assumed. Conversely, the existence of an unindexed branch is not sufficient for publication.

The publication rule does not upgrade evidence quality, alter experiment outcomes, or replace historical commits. It defines only the canonical reachability criterion for independent repository reconstruction.

## Retroactive application status

- **EXP-02:** reachable on `exp-03-spec`; publication candidate recorded in the index.
- **EXP-03:** reachable on `exp-03-spec`; publication candidate recorded in the index.
- **Q3b:** historical evidence chain is currently dangling and not present on an accessible branch/ref; therefore it is not yet publishable under this rule. Recovery must preserve the original evidence content and provenance.
