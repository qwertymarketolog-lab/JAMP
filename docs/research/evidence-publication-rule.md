# Evidence publication rule

## Canonical publication rule

JAMP uses **any-ref-with-index** for research evidence chains.

A closed experiment is canonically published when its evidence chain is reachable from the repository default branch (`main`) through an explicit reference in the canonical index `PROVENANCE.md` to the exact branch/ref and repository paths containing the evidence.

The evidence itself may remain on a dedicated branch. An auditor must not infer publication merely from the existence of an arbitrary branch.

This rule is the criterion for the retroactive publication audit of EXP-02, Q3b, and EXP-03.

## Retroactive application

### EXP-02

- Ref: `exp-03-spec`
- Evidence: `docs/research/exp-02-transfer.md`
- Evidence blob: `15df3fba6902678fc92df6a946c9dc6bb9e8ac6d`
- Recorded classification: `PARTIAL TRANSFER`

### EXP-03

- Ref: `exp-03-spec`
- Specification: `docs/research/EXP-03-SEARCH-TRANSFER.md`
- Specification blob: `9c8fd044a0b7fa0f328d1cdeb8067f9542d34a25`
- Evidence: `docs/research/EXP-03-EVIDENCE.md`
- Evidence blob: `2e674d02db7981cf5ef6b81d69171120f3eaf8c6`
- Recorded outcome: `B — TARGET PASS`

### Q3b

- Historical evidence chain: `ed686f52dc5162d7fab3ceb434bba106a85c0033` → `56218c31abad64fdda91f8789b7e7ff9d36bd7cf` → `80335f5b3ec29bae4998d184caeff02c7d5202a9`
- Intended evidence file: `docs/research/q3b-artifact-contract.md`
- Current publication status: **NOT REACHABLE**
- The recorded chain is currently dangling and is not present on an accessible branch/ref. It therefore does not satisfy this publication rule until the original evidence is recovered onto a reachable ref without changing its factual content.

## Audit rule

For reconstruction audits, the auditor reads only evidence reachable through the canonical index and the exact referenced refs/files. `main-only` is not assumed. Conversely, the existence of an unindexed branch is not sufficient for publication.

The publication rule does not upgrade evidence quality, alter experiment outcomes, or replace historical commits. It defines only the canonical reachability criterion for independent repository reconstruction.
