# Telegram → Runtime → OpenRouter E2E evidence (2026-10-20)

## Document class

This is an **integration E2E record**, not an `EXP-XX` research experiment.
Filed under `docs/research/` alongside EXP evidence for discoverability,
but it does not belong to the EXP series and must not be renamed to
`EXP-08-EVIDENCE.md` without a separate decision to formalize it as an experiment.

## Claim

A controlled **synthetic Telegram Update** traversed the JAMP webhook and Runtime, invoked the real OpenRouter API using the configured free-model override, and caused a Telegram Bot API reply to be delivered. The run returned a trace whose provenance retained the test-only override and did not grant model qualification.

This is a scoped integration observation, not a general claim that production Telegram ingress or persistent hosting is configured.

## Evidence anchor

- Repository: `qwertymarketolog-lab/JAMP`
- Workflow run: [39411112869](https://github.com/qwertymarketolog-lab/JAMP/actions/runs/39411112869)
- Job: `118588815555` — `e2e`, terminal conclusion `success`
- Tested commit: `bf89bbb1bea50cd3264dcb7d394cb360a7df05b7`
- Artifact: [`e2e-39411112869` (ID 12259661490)](https://github.com/qwertymarketolog-lab/JAMP/actions/runs/39411112869/artifacts/12259661490)
- Artifact SHA-256: `768fdc5f2548001ba4ebf7a018d1782e21428e4c1eb0aaab38d2c59724d33c26`
- Trace: `trace_97ace1c4`
- Frozen Core: `src/jamp/run.py` blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`; workflow emitted `FROZEN_CORE_DELTA=0`.

## Observed path

1. The workflow injected a synthetic Update into the public ngrok URL at `POST /v1/telegram/webhook`, with `X-Telegram-Bot-Api-Secret-Token` set to the configured workflow secret.
2. Webhook response was HTTP `200`, with status `EXECUTE` and a non-empty trace ID.
3. The injected message used `/search Ответь одним словом: JAMP_OK`.
4. The workflow fetched `/v1/provenance/trace_97ace1c4` and validated the execution record.
5. The user/operator separately observed the resulting `JAMP_OK` message arrive in Telegram.

The workflow job's terminal steps were successful: Frozen Core, secret validation, dependency install, import check, Uvicorn startup, ngrok startup, synthetic Update injection, response/provenance validation, and artifact upload.

## Provenance fields

The run log's successful provenance gate recorded:

```text
E2E_PASS trace_id=trace_97ace1c4
PROVIDER_REQUESTED_MODEL_ID=minimax/minimax-m3.1-flash:free
TEST_OVERRIDE=true
QUALIFICATION=NOT_GRANTED
```

The selected provider model was `minimax/minimax-m3.1-flash:free`. The request used the real OpenRouter integration, not a mocked provider. The test override is explicit, and qualification remains `NOT_GRANTED`; this observation must not be used to promote the model's qualification status.

## Artifact contents

Artifact `e2e-39411112869` contains six files:

- `uvicorn.log`
- `ngrok.log`
- `update.json`
- `response.json`
- `response.code`
- `provenance.json`

## Scope and non-claims

### Supported by this run

- The configured webhook secret was accepted by the JAMP endpoint for this request (HTTP 200, not an authentication refusal).
- The request passed the webhook's chat allowlist and update-idempotency gate, reached the `/search` execution path, and returned `EXECUTE`.
- Runtime/OpenRouter execution produced a trace with the recorded provider model and provenance fields.
- The workflow's terminal response/provenance assertions passed.
- The operator reported that the Telegram reply was received.

### Not established by this run

- **Authentic Telegram ingress:** the Update was injected by the workflow, not delivered by Telegram. The secret header was supplied by the test itself. This run does not verify `setWebhook`, Telegram's own signature/secret delivery, or a user-originated incoming message.
- **Persistent hosting:** the runner and ngrok tunnel were temporary and terminated after the job.
- **Model qualification:** `qualification=NOT_GRANTED` remains unchanged. A successful invocation is not qualification evidence.
- **PR merge readiness:** this E2E run is one gate only. Other CI, Ruff, mypy, baseline-integrity, review, and repository requirements must be assessed separately.
- **Exactly-once delivery across crashes:** SQLite update claiming prevents duplicate execution for a claimed update, but provider execution and Telegram reply are not one atomic transaction.

## Status

**E2E synthetic-path result: PASS for run 39411112869.**  
**Authentic Telegram ingress: NOT TESTED.**  
**Persistent hosting: NOT TESTED.**  
**Model qualification: NOT GRANTED.**  
**PR #371 merge decision: NOT DECIDED by this evidence record.**

Do not infer broader claims from this single run. Keep the run and artifact as the primary evidence anchors; this document is a durable index and scope statement, not a replacement for the raw evidence.


## Superseding run (2026-10-21)

Run 39534414865, commit 8c88eaf, trace_e82644ca supersedes the
transport evidence above with one addition: provider_model_id was
verified equal to provider_requested_model_id
(minimax/minimax-m3.1-flash:free). Prior run 39411112869 did not
record provider_model_id; its trace_97ace1c4 remains as precursor
evidence for the same transport path.

Frozen Core: 0fee0e1c..., delta=0.
qualification: NOT_GRANTED (test_override=true, unchanged).


## Summary diagnostics verification (2026-10-21)

Run 39561370652, commit d6d978c, trace_78d81146.

Criterion 7 (log identity, replacing earlier miscalibrated `>100 lines`):

  field_count                 11         PASS (exact allowlist)
  log_has_startup             true       PASS (Uvicorn startup marker found)
  log_bytes                   415        PASS (non-empty)
  log_lines_scanned           7          FACT (single-E2E log size, not a threshold)
  raw_log_content_included    false      PASS (script declaration)
  secret_values_emitted       false      PASS (script declaration)
  has_bot_pattern             false      PASS (grep)
  has_url_or_token            false      PASS (grep)

Artifact: e2e-39561370652, ID 12328245109, 1644 bytes, 5 files.
ngrok.log absent (sanitization requirement).

Verified: summary reads the correct Uvicorn log file and applies
the 11-field allowlist.

NOT verified: independent leak evidence. The original
`/tmp/uvicorn.log` is not retained in artifacts, so
`raw_log_content_included=false` and `secret_values_emitted=false`
are script declarations, not independently confirmed facts.
Verification here is structural (allowlist, identity, grep patterns),
not forensic.

Supersedes commit a733ecd / e33c029 for the summary implementation:
  e33c029 — escaping bug, superseded
  a733ecd — first summary, criterion 7 miscalibrated
  d6d978c — current: 11 fields, log_has_startup, log_bytes

## CI anomaly: import-historical.yml (2026-10-21)

OBSERVED
  Workflow:    import-historical.yml
  Run:         39652647763
  SHA:         bc41e034d99dff49b671a05c4cce6b4cd4a8d9ee
  Event:       push
  Branch:      feat/openrouter-telegram-mvp
  Conclusion:  failure
  Jobs:        []

OBSERVED
  on.push.branches on this SHA:
    - 'import/jamp-from-visual-merchant-hub'
    - '!main'
  Positive pattern does not match feat/openrouter-telegram-mvp.

EVIDENCE
  GitHub Community Discussion #210766 and actions/runner Issue #4001
  describe the same symptom: runs created for branches excluded by
  push filters, failing before any job is created.

INFERENCE
  Probable GitHub Actions platform defect. Causal link to this
  specific run is not independently proven.

REQUIRED CHECKS
  import-historical is not among the required contexts for main
  branch protection (required: Research Loop v0 Gate, G1 Trusted Lineage).

ACTION
  Documented. Workflow not modified. Not blocking PR #371.
  Not the cause of HOLD status.

Gate state on bc41e034:
  Required CI checks     PASS (18/18 check runs completed/success)
  import-historical      failure, non-blocking
  qualification          NOT_GRANTED
  PR #371                OPEN / DRAFT — HOLD

