# Telegram → Runtime → OpenRouter E2E evidence (2026-10-20)

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
