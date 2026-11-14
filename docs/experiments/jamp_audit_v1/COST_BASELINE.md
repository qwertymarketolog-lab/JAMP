# JAMP Audit v1 — Cost Baseline

## Current state

- Paid model requests: **0**.
- Monetary pricing formula: **UNKNOWN**.
- AnyModel `billing.coefficient` semantics and completeness across the 109 observed
  catalog entries: **UNKNOWN**.
- Token usage contract for chat/completions: **UNKNOWN**.
- USD cap: **NOT ENFORCEABLE** while provider pricing and billing semantics remain
  unknown. No synthetic USD ceiling is declared or implied.
- Every preflight and execution artifact records `cost_status: UNKNOWN_PRICING`. The PR-CI guardrail artifact writes this value with `execution_requested: false` and `catalog_preflight: NOT_RUN`; it performs no network request.

## Enforceable execution proxies

These are technical workload limits, not monetary limits:

| Proxy | Enforced value | Exact semantics |
| --- | ---: | --- |
| `MAX_PAID_REQUESTS` | 3 | Maximum number of paid request attempts handed to the HTTP transport in one experiment. A pre-send failure still consumes an attempt; no hidden retry is made. |
| `MAX_TOKENS_TOTAL` | 12,288 | Sum of configured `max_tokens` output ceilings for all catalog-available selected models, checked before execution. This is a requested-output ceiling, not actual provider usage and not prompt tokens. |
| `MAX_WALL_CLOCK_SECONDS` | 2,700 | Runner deadline measured from entry to `execute`. No new request starts unless at least one full 240-second request-timeout window remains. The GitHub Actions job has a 50-minute hard timeout as the outer kill boundary. |

The existing prompt-token estimate is a byte-based heuristic only. It is not used
as an enforceable token ceiling and is not a price estimate. Provider-reported
usage is recorded when returned, but its billing interpretation remains
**UNKNOWN**.

## Pricing consent gate

The workflow input `accept_unknown_pricing` defaults to `false`. A standalone
REFUSE check runs before the paid-execution step, including on pull requests where
`execute` is false. If pricing is unknown and the operator has not explicitly
set it to `true`, the check records `refuse_check: refused` and the paid step
remains blocked before any paid request. Setting it to `true` records consent to proceed
under unknown pricing; it does not establish a USD cap, pricing validity, or
qualification. The independent `execute=true` dispatch input is still required.

## Timeout and retry policy

- No automatic retries are implemented for paid requests.
- `PRE_SEND_NETWORK_ERROR` is used only for failures known to occur before a
  request could be sent (DNS resolution failure or connection refusal). It is
  safe to retry manually in a new, reviewed experiment; the runner does not retry.
- `POST_SEND_AMBIGUOUS` is used when transport failure occurs after entering the
  send operation and the provider may have processed the request. The runner
  records the outcome as **UNKNOWN**, does not retry, does not start later models,
  writes the partial manifest/metadata, and exits non-zero.
- HTTP error responses are recorded as `API_ERROR`; they are not automatically
  retried. Malformed responses are recorded as `INVALID_RESPONSE`.
- A request timeout is treated as `POST_SEND_AMBIGUOUS`, never as proof that
  the provider did not process or bill the request.

## First-run evidence gate

This file remains the fail-closed gate for expanding the first-run limit. The
runner treats the experiment as a first run unless it finds at least one valid
evidence block and every block has a complete manifest → usage → metadata chain.
More than three blocks, malformed values, missing files, or any inconsistency
keeps the first-run gate closed.

## Evidence block format

Add one block per model only after a real run and artifact have been independently
inspected. Values must be copied from raw evidence, not estimated. Each block
starts with `### model: <exact provider model id>` and contains these fields:
- `usage.prompt_tokens`: integer greater than 0
- `usage.completion_tokens`: integer greater than or equal to 0
- `source_run_id`: digits only
- `source_artifact_id`: digits only
- `manifest_file`: repository-relative path to the terminal manifest
- `metadata_file`: repository-relative path to model metadata JSON

Do not add a heading or placeholder block until the corresponding evidence exists.

The terminal manifest must map `metadata.model_key` to the exact
`metadata_file` path and contain the same provider-reported token usage under
`usage[model_key]`. Metadata must repeat the exact model ID, source Run ID,
source Artifact ID, and token counts. The runner checks the manifest → usage →
metadata chain in both directions; absent or conflicting usage keeps the gate closed. Booleans are not integers for this contract.
A block that cannot be followed to its raw source evidence is invalid.

## Recorded evidence

No evidence blocks are present. This is intentional; do not fabricate usage or
pricing values to unlock a larger run.
