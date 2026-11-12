# Stage 3 — Crosswalk and Provenance Evidence

**Recorded:** 2026-10-25  
**Scope:** Stock Audit and Financial Audit workflow runs on `da10830462e3d8d1061505db00ddc1b20240d6b7`.

## Interpretation contract

The configured OpenRouter Crosswalk in both audit workflows maps the JAMP-internal ID `am/nemotron-3-super-120b-a12b` to the provider-requested ID `z-ai/glm-5.3-flash`.

These fields describe different stages and are expected to differ under this mapping:

- `selected_model` / `requested_model_id`: JAMP-internal model identity requested by the experiment.
- `provider_requested_model_id`: provider model ID after applying the configured Crosswalk.
- `provider_model_id`: provider model ID recorded in the provenance trace.
- `evidence_details.provider_model`: provider-reported model label; in these runs it includes the dated suffix `z-ai/glm-5.3-flash-20260826`.

Therefore, the internal ID versus provider ID difference is **expected Crosswalk behavior**, not by itself a model-identity failure. The evidence documents execution through the mapped provider model; it does not prove that the provider executed the internal Nemotron model.

`evidence_status: VERIFIED` and `qualification: UNKNOWN` answer separate questions. The former records the execution/provenance verification status. The latter records that qualification of the model for the task has not been established by the qualification process. Do not reinterpret `UNKNOWN` as a failed execution or as a qualification PASS.

## Stock Audit evidence

- Workflow run: [40196033609](https://github.com/qwertymarketolog-lab/JAMP/actions/runs/40196033609)
- Job ID: `121176935676`, conclusion: `success`
- Artifact: `stock-provenance-evidence`, ID `12599509924`
- Trace ID: `trace_c9ff1e58`
- Request ID: `req_55491bbc`
- Provider: `openrouter`
- Selected/requested internal model: `am/nemotron-3-super-120b-a12b`
- Provider requested/model ID: `z-ai/glm-5.3-flash`
- Provider-reported model label: `z-ai/glm-5.3-flash-20260826`
- Provider response/generation ID: `gen-1792933549-Yirw4aFfwYbf0cja1HOy`
- `evidence_status`: `VERIFIED`
- `qualification`: `UNKNOWN`
- `status`: `EXECUTE`
- Required capabilities: `C01`, `C06`
- Artifact raw evidence SHA-256: `7785cbd5ae19704473b385b8b21ddbdf7cd9eeb06aee56ce0f66e7da7592f1f1`
- Frozen Core: `src/jamp/run.py`, expected blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`, `delta=0`.

## Financial Audit evidence

- Workflow run: [40196213021](https://github.com/qwertymarketolog-lab/JAMP/actions/runs/40196213021)
- Job ID: `121177487873`, conclusion: `success`
- Artifact: `financial-provenance-evidence`, ID `12600390954`
- Trace ID: `trace_920c98fe`
- Request ID: `req_de4ee4de`
- Provider: `openrouter`
- Selected/requested internal model: `am/nemotron-3-super-120b-a12b`
- Provider requested/model ID: `z-ai/glm-5.3-flash`
- Provider-reported model label: `z-ai/glm-5.3-flash-20260826`
- Provider response/generation ID: `gen-1792933693-qliWvUPL0xzPjSOK63VN`
- `evidence_status`: `VERIFIED`
- `qualification`: `UNKNOWN`
- `status`: `EXECUTE`
- Required capabilities: `C01`, `C06`
- Artifact raw evidence SHA-256: `7785cbd5ae19704473b385b8b21ddbdf7cd9eeb06aee56ce0f66e7da7592f1f1`
- Frozen Core: `src/jamp/run.py`, expected blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`, `delta=0`.
- Financial job log reports reference-value match: `[DATA MATCH] YES`; the provenance artifact's `qualification` remains `UNKNOWN`.

## Boundaries

- These are run-specific observations, not a universal qualification of the mapped model.
- The artifacts are GitHub Actions artifacts with 7-day retention, not permanent or signed certificates.
- The `crosswalk_digest` field is recorded as `sha256:local-model-id-map`; this value alone is not evidence of a cryptographic digest of the actual workflow mapping.
- No application code or Frozen Core changes are part of this note.
