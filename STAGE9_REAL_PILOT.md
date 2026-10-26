# Stage 9 — Real Pilot Evidence Record

**State:** VERIFIED  
**Recorded:** 2026-10-26  
**Scope:** One real HTTP execution through the configured OpenRouter provider, followed by the pilot's evidence/verdict and signature checks.

## Canonical GitHub Actions evidence

| Field | Value |
|---|---|
| Repository | [qwertymarketolog-lab/JAMP](https://github.com/qwertymarketolog-lab/JAMP) |
| Workflow | Real Pilot |
| Event | `workflow_dispatch` |
| Run ID | [40314338566](https://github.com/qwertymarketolog-lab/JAMP/actions/runs/40314338566) |
| Run conclusion | `success` |
| Job ID | [121543043161](https://github.com/qwertymarketolog-lab/JAMP/actions/runs/40314338566/job/121543043161) |
| Job conclusion | `success` |
| Tested source SHA | `940fec7c495ff2c890ff69b34f655e604fb20f68` |
| Artifact | [real-pilot-diagnostics-40314338566.zip](https://github.com/qwertymarketolog-lab/JAMP/actions/runs/40314338566/artifacts/12645573886) |
| Artifact ID | `12645573886` |
| Artifact SHA-256 | `35fdfac7a1c7cf1fad664fdb2ee44a69f5c894feae4c2b12b1b4dfeabab2fda7` |
| Artifact expiration | 2026-11-25T11:20:59Z |

## Observed execution result

The terminal log for the completed job records the pilot starting a real Uvicorn process, waiting for the HTTP server, and sending a real `/v1/execute` request.

| Field | Value |
|---|---|
| Provider | `openrouter` |
| Requested model ID | `z-ai/glm-5.3-flash` |
| Reported actual model ID | `z-ai/glm-5.3-flash` |
| Provider response / generation ID | `gen-1793013646-5SO1c6iZwmmflsdZXked` |
| Trace ID | `trace_a0e5d28e` |
| Evidence status reported by pilot | `VERIFIED` |
| Qualification reported by pilot | `QUALIFIED` |
| Signature check reported by pilot | `VALID` |

The log's extracted response reports:

- Revenue: **$1,000,000**
- Expenses: **$200,000**
- Profit: **$800,000**
- Margin: **80%**

Arithmetic check: `$1,000,000 - $200,000 = $800,000`; `$800,000 / $1,000,000 = 80%`.

## Verification boundary

This record establishes that the cited GitHub Actions run and job completed successfully and that their terminal log reported the values above. The model ID and response ID are recorded as reported by the pilot output; this document does not independently attest to OpenRouter's internal serving infrastructure.

`QUALIFIED` applies to this specific pilot execution and its configured checks. It does **not** by itself establish general qualification of all models, tasks, providers, or external integrations.

The pilot log reported `Signature: VALID`. The signature result is recorded as observed terminal evidence for this run, not as a claim that this Markdown file itself is cryptographically signed.

## Frozen Core

Expected blob SHA for `src/jamp/run.py`:

`0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

The file's blob SHA was checked on the tested `main` SHA `940fec7c495ff2c890ff69b34f655e604fb20f68` and matched the expected value. **Frozen Core delta: `0`.**

## Closure decision

**Stage 9 Real Pilot: VERIFIED for the scope described above.**

Canonical evidence remains the GitHub Actions Run → Job → terminal log and retained artifact linked above. This report is an index and human-readable record; it does not replace the underlying evidence.
