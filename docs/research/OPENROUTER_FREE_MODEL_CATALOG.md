# OpenRouter free-model discovery (research only)

## Purpose

Create a repeatable, keyless snapshot of the public OpenRouter model catalog, select entries whose catalog metadata explicitly reports zero prompt and completion price, and compare them with the existing JAMP 87-model crosswalk.

This is an additive research harness. It does not change Matrix v2, router policy, model qualification, provider execution, or Frozen Core `src/jamp/run.py`.

## Run from the repository root

```bash
python scripts/research/openrouter_free_catalog.py
```

The script uses the public `GET https://openrouter.ai/api/v1/models` endpoint and writes:

`artifacts/research/openrouter_free_model_catalog.json`

No API key is required for catalog discovery. The generated artifact is a timestamped observation and should be regenerated when current availability matters. It is not a static promise of continued access.

Optional arguments:

```bash
python scripts/research/openrouter_free_catalog.py --timeout 30
python scripts/research/openrouter_free_catalog.py --crosswalk artifacts/research/jamp_87_to_36_to_17_crosswalk.csv --output /tmp/openrouter-free-catalog.json
```

## Comparison semantics

- **Exact ID match:** the OpenRouter catalog ID is identical to a model ID in the existing crosswalk. This is a literal string comparison.
- **Name-stem candidate:** provider prefixes and a trailing `:free` suffix are removed for a search lead only. A candidate is explicitly marked `NAME_STEM_CANDIDATE_NOT_IDENTITY_PROOF`.
- Neither comparison proves that two providers expose the same model weights, revision, behavior, or service.
- The crosswalk is considered structurally valid only when it contains exactly 87 unique, non-empty `model_id` values. A different count is recorded as inconclusive rather than silently accepted.
- `openrouter/free` is recorded separately as a router entry, not counted as a specific model.
- Other entries are filtered only on explicit zero input and output prices. The catalog can include non-chat or multimodal offerings; this filter does not claim chat-completions compatibility.

## Evidence boundary

The generated artifact labels itself `PUBLIC_CATALOG_OBSERVATION_ONLY`. It explicitly records that JAMP execution approval, model-quality verification, and a live chat-completion test are false. Discovery must not change the existing evidence gate.

A model may proceed to a controlled provider-call test only after its exact OpenRouter ID, supported modality/endpoint, current access limits, and intended JAMP task profile have been checked. Live provider-call success is still not model qualification.

## Initial observation supplied during the 2026-10-18 audit

A public catalog request returned HTTP 200 and 471 catalog entries. The displayed filter produced 19 zero-price entries, including the `openrouter/free` router. That means the output contained 18 model entries plus one router entry. This was an initial observation, not a committed full catalog snapshot; rerun the script to produce the complete metadata artifact and current comparison results.
