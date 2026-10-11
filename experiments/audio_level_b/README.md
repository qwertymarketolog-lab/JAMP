# ArtifactNet Isolated Benchmark — Level B (Draft)

**Status:** OPEN / PREPARATION  
**Scope:** documentation-only experiment specification. No benchmark implementation, real-media result, or accuracy claim is included.

## 1. Purpose and isolation

Define a reproducible local benchmark for the ArtifactNet ONNX analyzer, outside JAMP's production/runtime path. The experiment must preserve raw analyzer outputs, target/model identity, provenance, and uncertainty. It must not modify the Frozen Core.

Frozen Core invariant:

- File: `src/jamp/run.py`
- Locked blob: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`
- Expected delta: **Δ = 0**

The existing JAMP audio adapter verifies input digests, passes the exact verified bytes to inference, and validates the returned evidence envelope. Its `VERIFIED` result validates the evidence procedure and envelope—not the truth or accuracy of the model's classification.

## 2. Model identity and integrity gate

| Field | Draft value |
|---|---|
| Model name | ArtifactNet |
| Version label | `v1.0-onnx` (provisional; pin the upstream revision before a run) |
| Format | ONNX |
| Target audio | Mono, 44.1 kHz |
| Windowing | Fixed-length windows/chunks according to the pinned model specification |
| License noted for this candidate | CC BY-NC 4.0; research/non-commercial use only |
| Expected size | 17,825,792 bytes (must be checked against the exact downloaded artifact) |
| Expected SHA-256 | **UNSET — do not run the benchmark until recorded and independently verified** |

Example manifest entry (intentionally blocked until the digest is known):

```json
{
  "model_name": "ArtifactNet",
  "version": "v1.0-onnx",
  "expected_sha256": "<UNSET: pin exact artifact and verify SHA-256>",
  "file_size_bytes": 17825792
}
```

Before inference, the runner must compute SHA-256 from the exact model bytes and compare it to the pinned expected digest. A missing digest, size mismatch, or digest mismatch blocks the run; it must not be replaced by a digest calculated during that same run and then treated as an independent expected value.

**Artifact identity remains unresolved:** determine whether the pinned model is one ONNX file or an ONNX file plus external tensor-data file(s). Record and hash every required artifact, with exact filenames, sizes, upstream revision/download source, and licenses. The byte-size value above is a draft assertion, not verified evidence.

## 3. Dataset manifest

File: `dataset_manifest.csv`

Every sample in the evaluation set must have one manifest row. Paths are relative to the benchmark root.

| Column | Type | Description |
|---|---|---|
| `sample_id` | string | Unique audio-recording identifier |
| `file_path` | string | Relative path to the local audio file |
| `sha256` | string | SHA-256 of the exact target file bytes |
| `label` | string | Ground-truth label: `original` or `synthetic` |
| `generator_source` | string | Generator/source identifier, e.g. `suno_v3`, `udio`, `human_live` |
| `split_type` | string | `train`, `val`, or `test` |

Required manifest gates:

- `sample_id` values are unique; labels and split names are from the declared sets.
- Verify each target SHA-256 before inference.
- Keep related recordings, variants, source tracks, and derivatives in a single split to reduce leakage; record the grouping rule and evidence for it.
- Fit/tune thresholds on `train`/`val` only. Do not use `test` to select thresholds.
- Preserve dataset provenance and label evidence. A filename or generator label alone is not proof of ground truth.
- Missing files, hash mismatches, duplicate IDs, unknown labels, or unresolved split leakage must be reported explicitly and must not silently become valid samples.

## 4. Draft configuration

File: `config.json`

```json
{
  "inference": {
    "batch_size": 1,
    "max_duration_sec": 30
  },
  "thresholds": {
    "synthetic_decision_threshold": 0.80,
    "human_decision_threshold": 0.20,
    "inconclusive_lower": 0.20,
    "inconclusive_upper": 0.80
  },
  "quality_gates": {
    "min_sample_rate": 44100,
    "reject_on_clipping": true
  }
}
```

The values are proposed experiment settings, not validated operating thresholds. Record the config file's SHA-256 with every run.

### Decision policy

Draft rule: an analyzer probability in the inclusive interval **[0.20, 0.80]** yields `INCONCLUSIVE`. Such samples are counted in the inconclusive rate and excluded from thresholded Precision/Recall/F1 calculations, but must remain in the raw results.

**Boundary clarification required before implementation:** the draft names 0.20 and 0.80 as both decision thresholds and inclusive inconclusive bounds. The intended strictness at exactly 0.20 and 0.80 must be fixed in a versioned protocol. Until then, boundary cases are unresolved and the benchmark gate remains HOLD.

The meaning and direction of the model's output score must also be verified against the pinned model interface before mapping it to a synthetic probability. Do not assume that a raw score is a calibrated probability.

### Audio quality gates

- Require a sample rate of at least 44.1 kHz as currently drafted; confirm whether the model instead requires exact 44.1 kHz input and define a pinned resampling procedure if needed.
- If `reject_on_clipping` is true, define a reproducible clipping detector and its threshold before the test run. Do not silently repair or discard samples.
- Define deterministic duration/windowing and aggregation (including partial final windows) from the pinned model specification.
- Record every quality-gate rejection and its reason in the results.

## 5. Runner and output files

Proposed runner: `benchmark.py`

The runner should operate locally and in isolation, without connecting the analyzer to the JAMP production runtime/API. It should record:

- repository revision or experiment package revision;
- Python/runtime and dependency versions, platform, inference provider, and relevant execution settings;
- hashes and sizes for the model artifacts, config, manifest, and every target file;
- start/end timestamps with timezone, sample-level status, and any exception/error;
- exact raw analyzer output separately from normalized score and final benchmark decision.

Outputs:

- `results/raw_predictions.jsonl` — one record per manifest sample, including `sample_id`, target digest, split, label, raw model output, normalized score (if supported by the pinned interface), thresholded decision/status, quality-gate outcome, error/reason, and provenance.
- `results/metrics.json` — aggregate metrics, denominators, coverage, exclusions, protocol/config/model/dataset digests, and run metadata.

Do not overwrite raw outputs. A rerun should produce a separate run directory or uniquely identified output set.

## 6. Test-split metrics

Calculate on `test`:

- Precision, Recall, and F1 for class `synthetic`;
- AUROC;
- Inconclusive Rate;
- False Positive Rate (FPR) on `original` tracks.

Every metric must include its numerator/denominator and sample scope. Report total test count, successfully scored count, classified count, inconclusive count, quality-gate rejects, inference errors, and class counts.

**Metric protocol decisions still required:**

1. Precision/Recall/F1 and FPR are proposed to exclude `INCONCLUSIVE` decisions; therefore report them as conditional-on-classified metrics and report classified coverage beside them.
2. AUROC ordinarily requires continuous scores, not thresholded decisions. Specify whether it uses all valid test scores, including samples whose thresholded decision is `INCONCLUSIVE`. If scores are missing or invalid, report the affected count and do not silently impute values.
3. Define how inference failures and quality-gate rejects enter the coverage denominator and whether any metric is withheld when score coverage is incomplete.
4. Define confidence intervals and the grouping/resampling unit before comparing models or claiming generalization.

No metric should be reported as a benchmark result until these choices are versioned and the test split has not been used for tuning.

## 7. Reproducibility and interpretation

- Pin the upstream model revision, dependencies, inference provider, and dataset manifest.
- Preserve raw outputs and errors; never synthesize predictions for failed inference.
- Repeat inference on a fixed subset in the pinned environment and compare raw outputs/scores to empirically test repeatability. Do not claim determinism before this experiment.
- Keep all threshold selection on `train`/`val`; run the frozen test protocol once per declared evaluation version.
- Model outputs and their probabilities are analyzer-reported values. They are not presumed calibrated or comparable across tools without separate evidence.
- Results on one dataset do not establish general-world accuracy or production readiness.

## 8. License boundary

This draft treats ArtifactNet as a **research/non-commercial candidate** under the stated CC BY-NC 4.0 model license. Review the exact model, data, and dependency licenses and notices before downloading/distributing artifacts or using results commercially. This specification does not grant commercial-use permission.

## 9. Current gate/state

**STATE: OPEN / PREPARATION (benchmark gate: HOLD)**

Blocking items:

- expected model artifact SHA-256 is unset;
- exact model artifact bundle and its byte size are not yet verified;
- output-score semantics and audio preprocessing/windowing are not yet pinned;
- threshold boundary policy and metric denominators need versioned decisions;
- no independent JAMP test-set results or repeatability experiment exist yet.

No model accuracy, reproducibility, determinism, or production-readiness claim is made by this document.
