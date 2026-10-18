# OpenRouter free-model discovery (research only)

## Purpose

Create a repeatable, keyless snapshot of the complete public OpenRouter model catalog, preserve all returned model metadata, and separately select entries whose catalog metadata explicitly reports zero prompt and completion price.

This is an additive research harness. It does not change Matrix v2, router policy, model qualification, provider execution, or Frozen Core `src/jamp/run.py`. It is independent of the AnyModel catalog and crosswalk.

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
python scripts/research/openrouter_free_catalog.py --output /tmp/openrouter-free-catalog.json
```

## Catalog semantics

- Entries are included only when both prompt and completion prices are explicitly numeric/string zero.
- `openrouter/free` is recorded separately as a router entry, not counted as a specific model.
- Concrete free model IDs are preserved exactly as OpenRouter returns them.
- The catalog may contain non-chat or multimodal offerings; zero pricing does not establish chat-completions compatibility.
- This script does not compare OpenRouter models to AnyModel, infer identity across providers, or alter JAMP model selection.

## Evidence boundary

The generated artifact stores the complete returned catalog in `all_models`, the filtered zero-price concrete model list in `models`, and the router separately. The generated artifact labels itself `PUBLIC_CATALOG_OBSERVATION_ONLY`. It explicitly records that JAMP execution approval, model-quality verification, and a live chat-completion test are false. Discovery must not change the existing evidence gate.

A model may proceed to a controlled provider-call test only after its exact OpenRouter ID, supported modality/endpoint, current access limits, and intended JAMP task profile have been checked. Live provider-call success is still not model qualification.

## Initial observation supplied during the 2026-10-18 audit

A public catalog request returned HTTP 200 and 471 catalog entries. The displayed filter produced 19 zero-price entries, including the `openrouter/free` router. That means the output contained 18 concrete model entries plus one router entry. This was an initial observation, not a full catalog snapshot. The 18 model entries and separate router entry are preserved in `artifacts/research/openrouter_free_model_catalog_initial_observation.json`; the full API response was not preserved. Rerun the script to produce a complete metadata artifact and current results.


## Controlled live chat-completion probes

After generating the complete catalog, a controlled probe can send one short text request to each selected zero-price text-output model. The default is limited to five models per run:

```bash
export OPENROUTER_API_KEY='...'
python scripts/research/openrouter_probe_free_models.py
```

Review the output artifact at `artifacts/research/openrouter_free_model_probe.json`. To probe every eligible model, pass `--limit 0`; this deliberately requires an explicit opt-in because provider rate limits and temporary availability can vary. The probe records HTTP status, latency, response ID, reported model and usage where available. It never records the API key, prompt response text, or raw provider error body. A `CHAT_COMPLETION_OK` is a single-time connectivity result only, not a JAMP qualification or permission to route tasks to the model.
