# EXP-MILLENNIUM-RIEMANN-V0 — independent AI research sensor experiment

## Contract

- Frozen Core is unchanged; `src/jamp/run.py` is not modified.
- Provider: AnyModel OpenAI-compatible API.
- Sensors: the same five models used by EXP-MULTI-AI-V0.
- All five sensors receive the identical system prompt, identical Riemann Hypothesis task, and `temperature=0`.
- Each raw model response is preserved before any normalization.
- A model may report only one of:
  - `PROOF_CLAIM`
  - `DISPROOF_CLAIM`
  - `UNKNOWN`
- A claimed proof or disproof is **not** a verified mathematical result merely because a model asserts it.
- JAMP does not use majority voting as mathematical authority.
- The V0 artifact records observations and deterministic relations; independent mathematical verification remains a separate evidence step.
- Missing, malformed, or failed observations remain `UNKNOWN` and are never synthesized.

## Task

> Prove or disprove the Riemann Hypothesis: every non-trivial zero of the Riemann zeta function \(\zeta(s)\) has real part \(1/2\).

Each sensor must distinguish:
1. established theorem/results it relies on;
2. its proposed argument;
3. every critical step;
4. every unproved dependency or assumption;
5. whether it actually claims a complete proof, a disproof, or no resolution.

## Required response schema

Each model must return JSON with exactly these keys:

```json
{
  "status": "PROOF_CLAIM | DISPROOF_CLAIM | UNKNOWN",
  "claim": "short statement",
  "key_lemmas": ["..."],
  "critical_steps": ["..."],
  "unproved_dependencies": ["..."],
  "evidence": ["..."],
  "uncertainty": "..."
}
```

## Arbitration boundary

The experiment must distinguish:

- `OBSERVED`: the model returned parseable structured data.
- `UNKNOWN`: no valid observation was obtained.
- `PROOF_CLAIM` / `DISPROOF_CLAIM`: a model claimed a resolution.
- `UNVERIFIED_CLAIM`: a resolution claim exists but no independent mathematical verification has established it.

A model's confidence is not evidence of correctness.

## Execution

Set `ANYMODEL_API_KEY` and run:

```bash
PYTHONPATH=.:src python scripts/research/exp_millennium_riemann_v0.py
```

Default artifact:

`artifacts/research/exp_millennium_riemann_v0.json`

A non-zero exit code means at least one sensor did not produce an observation. It is not a judgement on the Riemann Hypothesis.
