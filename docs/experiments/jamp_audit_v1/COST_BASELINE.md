# JAMP Audit v1 — Cost Baseline

## Current state

- Paid model requests: **0**.
- Monetary pricing formula: **UNKNOWN**.
- AnyModel `billing.coefficient` semantics and completeness across the 109 observed
  catalog entries: **UNKNOWN**.
- Token usage contract for chat/completions: **UNVERIFIED**.
- No cost or qualification estimate may be inferred from model IDs alone.

This file is also the fail-closed gate for expanding the first-run limit. The
runner treats the experiment as a first run unless it finds at least one valid
evidence block and every block has a complete manifest → usage → metadata chain.
More than three blocks, malformed values, missing files, or any inconsistency
keeps the first-run gate closed.

## Evidence block format

Add one block per model only after a real run and artifact have been independently
inspected. Values must be copied from raw evidence, not estimated. Do not populate
this template before the corresponding source run and artifact exist.

```text
### model: <exact provider model id>
usage.prompt_tokens: <integer greater than 0>
usage.completion_tokens: <integer greater than or equal to 0>
source_run_id: <digits>
source_artifact_id: <digits>
manifest_file: <repository-relative path to terminal manifest>
metadata_file: <repository-relative path to model metadata JSON>
```

The terminal manifest must map `metadata.model_key` to the exact
`metadata_file` path. Metadata must repeat the exact model ID, source Run ID,
source Artifact ID, and token counts. Booleans are not integers for this contract.
A block that cannot be followed to its raw source evidence is invalid.

## Recorded evidence

No evidence blocks are present. This is intentional; do not fabricate usage or
pricing values to unlock a larger run.
