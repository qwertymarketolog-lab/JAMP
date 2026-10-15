# EXP-OSINT-V1 — Contract

**Version:** v1  
**State:** EXECUTION CONTRACT  
**Purpose:** cross-model OSINT retrieval audit through AnyModel.

## Frozen task
Each cohort model receives the same prompt:

> Determine whether Pluto is classified as a planet under the International Astronomical Union (IAU) 2006 definition. Return a concise answer, the decisive factual basis, and the URLs of the sources you relied on. Do not invent URLs. If you cannot retrieve or verify a source, say so.

Model-provided URLs are observations, not independently verified facts.

## Cohort
1. Fetch `GET https://anymodel.org/v1/models`.
2. Record the exact catalog response and SHA-256 digest.
3. Select every catalog model except the exact alias `am/free`.
4. The resulting cohort MUST contain exactly 86 model IDs.
5. Any other cardinality is HOLD; no model probes are sent.
6. Sort IDs lexicographically and freeze the list in the artifact.

## Probe
- Endpoint: `https://anymodel.org/v1/chat/completions`
- Secret: `ANYMODEL_API_KEY`
- Temperature: 0
- Max tokens: 500
- Timeout: 45 seconds
- Concurrency: 8

## Raw evidence
Each model records run ID, timestamp, model ID, HTTP status, elapsed time, raw response, answer text, observed URLs, and error.

No majority vote, LLM judge, synthetic PASS, or inferred capability verdict.

## Terminal artifact
`artifacts/research/exp_osint_v1_<run_id>.json`

## Frozen Core
`src/jamp/run.py` expected blob: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.