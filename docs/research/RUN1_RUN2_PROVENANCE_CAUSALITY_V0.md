# RUN1_RUN2_PROVENANCE_CAUSALITY_V0

## Objective

Determine the smallest evidence-backed explanation set for divergences between AnyModel availability Run 1 and Run 2, without assuming causality.

Primary question:

> Why did 87 models × 3 attempts produce 50 identical sequences and 37 differing sequences between Run 1 and Run 2?

The task MUST preserve competing hypotheses and conclude `CAUSALITY_NOT_ESTABLISHED` unless causal evidence satisfies the requirements below.

## Scope / Frozen Core

- Repository: qwertymarketolog-lab/JAMP
- Frozen Core: `src/jamp/run.py`
- Locked blob: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`
- Required invariant: `Δ(src/jamp/run.py)=0`
- No workflow/test/threshold/contract/provenance change may be made merely to obtain a preferred result.

## Inputs

### Run 1

- Artifact: `artifacts/research/anymodel_availability_n3.json`
- Content SHA256: `d33e4a555771a323d040ee13e1afd0e28f15cc3b9751e5e0a26ab41933cfdc08`
- Git blob SHA: `13bcc9407e7a77d09ea0f2f631d903ba8dcfaae2`
- Source commit: `69163272b7079d7883997b687c202647640b425d`
- Contract: 87 models × 3 attempts

### Run 2

- Artifact: `artifacts/research/anymodel_availability_n3_run2.json`
- Content SHA256: `de0e31f62f6c1876fc91be2710fd2f4f5de956e99549ea752220c2790b52a2ee`
- Git blob SHA: `ca231bdadcdafa302dcda131d19244f30bdf3066`
- Evidence digest: `sha256:5fd8ba754fb1cb2d1169d82d014cf079124cec2953602f96cf5ef7223f05ef89`
- Catalog digest: `sha256:f8c52a3aac28fdd9a9929b0a9bd1dbe2c3e8755c78e760f59bf9962ce1f59823`
- Source commit: `36c6f23da600b37d45718530cfa693a69f498bfc`
- Contract: 87 models × 3 attempts

### Harness / provenance

- Harness origin: `3e105b17656018e37eb748dca73129c231b3de46`
- Run 1 artifact addition: `69163272b7079d7883997b687c202647640b425d`
- Run 2 artifact addition: `36c6f23da600b37d45718530cfa693a69f498bfc`
- Comparator: `scripts/research/compare_anymodel_availability_runs.py`
- Comparator compares common transport signature: `(status_code, timed_out)`
- Current endpoint: `https://anymodel.org/v1`
- Timeout: 30 s
- Temperature: 0
- Prompt: `Reply with exactly: OK`

## Observed divergence baseline

The comparator has established:

- Common models: 87/87
- Run size: 87 × 3 for both
- Identical attempt sequences: 50/87
- Different attempt sequences: 37/87
- Of the 37 differences: 30 recovery patterns, 3 regression patterns, 4 non-200 composition changes
- Run 2 probe order matched its catalog snapshot order: 87/87, 0 inversions
- xAI Run 2: 8 chat models × 3 = 24 HTTP 200; 2 image models × 3 = 6 HTTP 400
- Run 2 xAI responses included cf-ray; image attempts included x-request-id; no observed retry/rate-limit headers in the preserved Run 2 evidence.

These are baseline observations, not causal conclusions.

## Hypotheses

H1 — Catalog/order effect:
A different model ordering or catalog snapshot changed temporal/provider load conditions.

H2 — Temporal/server-state effect:
The provider's server-side state changed between Run 1 and Run 2 independently of JAMP code.

H3 — Provider-specific transient behavior:
Divergence is concentrated in particular providers/models and reflects transient upstream behavior.

H4 — Rate-limit/retry behavior:
429/503 and recovery patterns are associated with retry/rate-limit signals.

H5 — Transport/network effect:
Timeouts, 4xx/5xx responses, or network/intermediary behavior explain some divergence.

H6 — Harness/environment effect:
Endpoint, authentication, timeout, runtime, environment, or harness behavior differs materially between runs.

H7 — Evidence-schema/provenance effect:
Differences in preserved evidence or artifact creation obscure otherwise comparable observations.

H8 — Mixed cause:
More than one of H1–H7 contributes.

The task MUST NOT assume any hypothesis is true.

## Required investigations

### A. Provenance

Verify, from repository evidence:

- exact artifact source commits;
- exact Git blob identities;
- exact raw-content SHA256 where raw bytes are obtainable;
- harness commit ancestry;
- endpoint/configuration changes;
- catalog identity/order;
- repository changes between executions.

### B. Divergence matrix

Produce per-model:

- Run 1 sequence;
- Run 2 sequence;
- first differing attempt;
- divergence class;
- provider/model;
- Run 2 timing where available;
- available transport/status fields.

### C. Temporal analysis

For every differing model, use preserved `observed_at` values where available.

Report:

- absolute UTC timeline;
- clustering by provider;
- clustering by status;
- whether divergence precedes/follows identifiable events.

Do not infer causality from temporal adjacency alone.

### D. Header analysis

For preserved Run 2 headers, extract and correlate:

- `retry-after`
- `x-ratelimit-*`
- `x-request-id`
- `cf-ray`
- `x-should-retry`

Do not issue new AnyModel requests solely to fill missing historical evidence.

Missing headers in Run 1 remain UNKNOWN.

### E. Order analysis

Compare catalog/order identity and execution positions.

Test whether divergence is associated with:

- absolute position;
- provider blocks;
- changed positions;
- time since run start;
- neighboring requests.

Report correlation only as correlation.

### F. Harness/environment analysis

Compare commits and runtime contract.

Explicitly identify any variable that changed and any variable that is only assumed unchanged.

Code inspection alone is not runtime evidence.

### G. Alternative explanations

For every leading hypothesis, record:

- supporting evidence;
- contradicting evidence;
- missing evidence;
- whether evidence is direct or indirect;
- whether the hypothesis is falsifiable with existing artifacts.

## Evidence levels

Each finding MUST be tagged:

- `OBSERVED`: directly present in artifact/log/GitHub evidence.
- `VERIFIED`: independently checked against a second authoritative representation.
- `INFERRED`: interpretation supported by observations but not directly demonstrated.
- `UNKNOWN`: required evidence absent or unrecoverable.

Never convert `INFERRED` to `VERIFIED` by repetition.

## Causality gate

A causal claim for hypothesis H is permitted only if all are true:

1. Temporal ordering is compatible.
2. The candidate cause is directly observed, not inferred solely from outcome.
3. The relevant exposure differs between runs or observations.
4. The outcome difference is measured.
5. At least one plausible competing explanation is tested and not sufficient.
6. The evidence is not solely based on correlation, catalog position, or provider identity.
7. No known evidence contradiction remains unresolved.
8. The causal scope is explicitly limited to the observations covered.

If any condition fails:

`CAUSALITY_NOT_ESTABLISHED`

This does NOT mean the hypothesis is false.

## State machine

`OPEN`
→ task inputs/provenance accepted

`RUNNING`
→ evidence collection/analysis in progress

`VERIFIED`
→ requested factual/provenance claims independently established

`INCONCLUSIVE`
→ divergence established but no causal explanation satisfies the causality gate

`FAILED`
→ an explicit contract invariant is violated or required evidence is corrupted/unusable

`HOLD`
→ required evidence is unavailable, access is blocked, or a safe conclusion cannot be made

`CLOSED`
→ final evidence package, contradictions, limitations, and state are persisted

Allowed transitions MUST be evidence-backed. No `RUNNING → VERIFIED` for causal claims without the causality gate.

## Output contract

Persist a machine-readable result containing:

- task ID;
- input artifact hashes/blob IDs;
- source commits;
- harness/configuration identity;
- baseline divergence counts;
- per-model divergence matrix;
- hypothesis records;
- evidence references;
- contradictions;
- unknowns;
- causal-gate result per hypothesis;
- final state;
- analysis timestamp;
- analyst/tool provenance.

Recommended final states:

- `INCONCLUSIVE` when 37/87 divergence is verified but causality is not established.
- `HOLD` when required evidence cannot be retrieved.
- `VERIFIED` only for factual/provenance subclaims that meet verification requirements.
- `CLOSED` only after the evidence package itself is complete.

## Explicit non-goals

- No new AnyModel probes merely to make the historical comparison complete.
- No threshold changes.
- No Frozen Core changes.
- No workflow changes to obtain GREEN.
- No LLM judge/majority vote.
- No metadata-only model identity inference.
- No synthetic reconstruction of missing Run 1 headers/timestamps.
- No claim that 37 divergences have a single root cause unless the causality gate is satisfied.

## Final decision rule

The task answers:

> What do the existing Run 1 and Run 2 evidence actually establish, what competing explanations remain, and what evidence would be required to establish causality?

It MUST NOT answer:

> Which hypothesis feels most likely?

Final causal status is one of:

- `CAUSALITY_ESTABLISHED`
- `CAUSALITY_NOT_ESTABLISHED`
- `HOLD_INSUFFICIENT_EVIDENCE`

Default is `CAUSALITY_NOT_ESTABLISHED` unless the gate is explicitly satisfied.
