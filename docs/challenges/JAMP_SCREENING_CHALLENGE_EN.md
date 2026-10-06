# JAMP Screening Challenge
## Deterministic Capability Router

**Time:** 1.5–2 hours  
**Language:** Python 3.11+  
**Format:** take-home / Git repository

## Goal

Build a small deterministic Capability Router for JAMP.

The router receives a task, evaluates capability evidence and makes one of two decisions:

- **EXECUTE** — execution is allowed;
- **REFUSE** — execution is not allowed.

Core principle:

> **Insufficient evidence is not permission to execute.**

`UNKNOWN` and `INCONCLUSIVE` must never automatically become `EXECUTE`.

## 1. API

Implement:

`POST /v1/route`

Example request:

```json
{
  "task_id": "task-001",
  "required_capability": "text_generation",
  "payload": {
    "prompt": "Write a short product description"
  }
}
```

Example result:

```json
{
  "decision": "EXECUTE",
  "selected_provider": "provider_a",
  "evidence": {
    "capability": "text_generation",
    "status": "VERIFIED"
  },
  "routing_reason": "provider_a has VERIFIED evidence for the required capability"
}
```

For refusal:

```json
{
  "decision": "REFUSE",
  "selected_provider": null,
  "evidence": {
    "capability": "text_generation",
    "status": "UNKNOWN"
  },
  "routing_reason": "required capability is not sufficiently verified"
}
```

## 2. Providers

Implement at least two mock providers:

- `provider_a`
- `provider_b`

Each provider must expose capability evidence.

For example:

```text
provider_a:
  text_generation = VERIFIED

provider_b:
  text_generation = UNKNOWN
```

Provider selection must be **deterministic**.

If multiple providers have `VERIFIED` evidence, use an explicitly documented deterministic rule, such as lexicographic ordering.

## 3. Required behavior

The router must implement:

| Evidence | Decision |
|---|---|
| `VERIFIED` | `EXECUTE` |
| `UNKNOWN` | `REFUSE` |
| `INCONCLUSIVE` | `REFUSE` |
| missing | `REFUSE` |

Additionally:

- unknown capability → `REFUSE`;
- provider timeout/error → handle explicitly without claiming success;
- no suitable provider → `REFUSE`;
- routing result must contain evidence;
- routing result must explain the decision;
- identical input must produce identical routing results.

### Negative case

This case is mandatory:

```text
provider_a = UNKNOWN
provider_b = UNKNOWN
→ REFUSE
```

And:

```text
provider_a = VERIFIED
provider_b = UNKNOWN
→ EXECUTE provider_a
```

Do not implement:

```text
UNKNOWN → try a provider anyway
```

## 4. Tests

Use `pytest`.

At minimum, include tests for:

1. `VERIFIED → EXECUTE`;
2. `UNKNOWN → REFUSE`;
3. `INCONCLUSIVE → REFUSE`;
4. missing evidence → `REFUSE`;
5. unknown capability → `REFUSE`;
6. deterministic provider selection;
7. provider error;
8. provider timeout;
9. no fallback when evidence is `UNKNOWN`;
10. identical result for identical input.

Determinism should be tested with at least **100 identical runs**.

## 5. Architecture

You are not expected to build a production platform.

We expect a small, clear architecture with separation between:

```text
API
 ↓
Capability Router
 ↓
Evidence / Capability Model
 ↓
Provider Adapter
```

Do not put all logic into a single endpoint or giant service class.

Provider-specific details should be isolated behind an adapter/interface.

## 6. README

The README must include:

- short solution overview;
- requirements;
- local setup;
- test commands;
- API request/response example;
- routing policy;
- deterministic selection rule;
- behavior for `UNKNOWN` / `INCONCLUSIVE`;
- short explanation of architectural decisions.

## 7. Docker

Provide:

- `Dockerfile`;
- `docker-compose.yml` if needed;
- startup instructions.

The solution must run without proprietary API keys.

## 8. Evaluation

**100 points:**

| Area | Points |
|---|---:|
| Correct routing semantics | 25 |
| Fail-closed behavior | 20 |
| Deterministic selection | 15 |
| Tests / edge cases | 15 |
| Architecture / separation of concerns | 10 |
| Evidence + provenance in result | 10 |
| README / reproducibility | 5 |

### Critical mistakes

The following are serious issues:

- `UNKNOWN → EXECUTE`;
- random provider fallback;
- non-deterministic routing;
- weakening/deleting tests to obtain PASS;
- hardcoded secrets;
- missing negative-path tests;
- non-reproducible execution.

## 9. Submission format

Provide a Git repository with a structure similar to:

```text
jamp-screening/
├── app/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

The exact structure is up to you.

The repository must contain:

- source code;
- tests;
- Docker configuration;
- README;
- Git commit history.

### Submission

Send the repository link together with a short note containing:

- time spent;
- what you implemented;
- assumptions you made;
- what you would improve with additional time.
