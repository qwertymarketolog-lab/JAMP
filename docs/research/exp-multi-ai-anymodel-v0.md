# EXP-MULTI-AI-V0 — AnyModel federation sensor experiment

## Contract

- Frozen Core: unchanged; `src/jamp/run.py` remains blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.
- Provider: AnyModel OpenAI-compatible API.
- Sensors: exactly five currently listed free models:
  - `am/diffusiongemma-26b-a4b-it`
  - `am/gpt-oss-20b`
  - `am/laguna-xs-2.1`
  - `am/llama-3.2-11b-vision-instruct`
  - `am/mistral-nemotron`
- Same system prompt, same user question, temperature 0.
- Raw response is preserved before derivation.
- Deterministic conflict matrix:
  - `AGREEMENT`: both observations are valid and normalized `answer` strings are equal.
  - `CONFLICT`: both observations are valid and normalized `answer` strings differ.
  - `UNKNOWN`: an observation failed or has no structured answer.
- No model majority is treated as truth.
- The experiment is read-only with respect to JAMP semantics.

## Execution

Set `ANYMODEL_API_KEY` in the environment and run:

```bash
PYTHONPATH=.:src python scripts/research/exp_multi_ai_anymodel_v0.py
```

Default artifact:

`artifacts/research/exp_multi_ai_anymodel_v0.json`

A non-zero exit code means at least one of the five sensors did not produce an observation; this is not a synthetic PASS/FAIL judgement about the question itself.
