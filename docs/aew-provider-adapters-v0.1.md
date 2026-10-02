# AEW v0.1 Provider Adapter Design

Status: DESIGN-ONLY

Base: `main` at the PR base commit for this change.

## Scope

Define the minimal adapter boundary for three provider families:

- Gemini
- Claude
- GPT

This PR defines contracts only. It does not implement HTTP clients, SDK calls, authentication, retries, provider fallback, pricing lookup, or real API execution.

## Boundary

`provider adapter -> ModelBudgetPolicy -> AIWorker -> WorkerObservation`

The adapter MUST:

1. identify provider and model;
2. accept an AEW task/context;
3. require budget authorization before a prospective call;
4. return a `WorkerObservation` on a permitted execution;
5. preserve provider/model identity and hashes needed for provenance.

The adapter MUST NOT:

- write `VERIFIED` evidence directly;
- mutate `EvidenceLedger`;
- perform implicit provider fallback/escalation;
- guess token/cost estimates;
- bypass `ModelBudgetPolicy`.

## Three design targets

| Provider | Adapter ID | Real API calls in this PR |
|---|---|---|
| Gemini | `gemini` | forbidden |
| Claude | `claude` | forbidden |
| GPT | `gpt` | forbidden |

## Fail-closed requirements

A call is denied when budget authorization is missing or returns denied. Missing token/cost estimates remain UNKNOWN and therefore denied under the existing AEW `ModelBudgetPolicy`.

Provider errors, malformed responses, missing provenance fields, and transport failures must become observations/errors for later evidence handling; they must not be promoted to VERIFIED automatically.

## Frozen Core

`src/jamp/run.py` is out of scope. Required invariant: `Δ(src/jamp/run.py)=0`.

## Explicit non-goals

- no API keys or secrets;
- no workflow dispatch;
- no provider SDK dependencies;
- no real network calls;
- no model selection/ranking;
- no changes to AEW state semantics;
- no changes to EvidenceLedger semantics.

## Next implementation gate

Before implementing a provider adapter, add contract tests that prove:

1. budget authorization is mandatory;
2. denied budget produces no provider call;
3. provider/model identity is retained;
4. adapter output is a `WorkerObservation`;
5. adapter cannot directly promote evidence to `VERIFIED`;
6. real API execution remains disabled in the contract-test path.
