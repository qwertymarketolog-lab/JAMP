Stock Audit v2 — evidence boundary

This experiment sends 24 user-supplied prompts through a real local Uvicorn HTTP server backed by JAMP and OpenRouter. For expected VERIFIED cases, the harness requires status=EXECUTE, evidence_status=VERIFIED, a signed verdict accepted by /v1/verify-verdict, and persisted provenance. T07 requires refusal/inconclusive behavior; T23 passes only on explicit refusal/inconclusive and fails if JAMP executes the adversarial prompt.

Critical limitation: the prompts contain claims about stock drawdowns, IPO plans, growth rates, market share and company status. These are inputs, not independently verified reference data. This harness does not compare claims or generated financial analysis against MOEX ISS, issuer filings or another ground-truth source. VERIFIED means the configured JAMP evidence/verdict path passed for the request; it does not prove financial correctness. T23 tests refusal behavior for the supplied adversarial name, not a global proof that no such company exists.

The workflow is manual-only, requires OPENROUTER_API_KEY and JAMP_SIGNING_KEY, and uploads report, per-case results, Uvicorn log and provenance JSONL even on failure. No changes to src/jamp/run.py are part of this experiment.
