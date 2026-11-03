# The Hunt Benchmark v0.2 — Specification

**Status:** SPECIFICATION / NOT IMPLEMENTED  
**Scope:** Research benchmark only. This document does not implement or qualify JAMP runtime behavior.  
**Repository branch:** `exp/hunt-v0.2-benchmark`

## 1. Objective

Measure the effectiveness of JAMP's Evidence Engine against a Baseline in detecting hallucinated Python packages, using an independently verified and locked Ground Truth (GT) and identical model inputs.

The benchmark measures PyPI distribution-name presence at a recorded observation time. It does **not** establish package safety, package quality, importability, API compatibility, or global non-existence outside PyPI.

No target threshold for success is predefined. Results are reported as observations, including uncertainty and conflicts.

## 2. Pipeline Architecture

1. **Candidate Generation**
   - Generate 200 candidates: 100 sourced real-package candidates and 100 plausible generated-name candidates.
   - Candidate origin is metadata only; it is not Ground Truth.
   - Enforce uniqueness both on original identifiers and after PEP 503-style normalization. A collision is recorded and resolved before verification; it must not be silently discarded.
   - Record the generation method, version, and random seed (if randomness is used).

2. **Independent Ground Truth Verification**
   - Query the PyPI JSON API for every normalized candidate.
   - Apply a minimum delay of `time.sleep(0.1)` between consecutive requests.
   - Preserve the raw response bytes and calculate SHA-256 over those exact bytes. For responses without a body, record that no response body was available; do not fabricate a digest.
   - Verify the returned distribution name against the requested normalized name.
   - Allowed statuses:
     - `EXISTS_ON_PYPI`: successful response and matching normalized distribution name.
     - `NOT_FOUND_ON_PYPI`: authoritative HTTP 404 for the requested PyPI JSON endpoint.
     - `INCONCLUSIVE`: timeout, connection failure, rate limit, server error, malformed response, or otherwise insufficient evidence.
     - `AMBIGUOUS`: response is structurally valid but conflicts with the requested identity or cannot be unambiguously attributed to it.
   - Candidate-origin labels must never override the observed result.

3. **Ground Truth Lock**
   - Produce `manifest.json`, `observations.jsonl`, raw response files, and a SHA-256 checksum manifest.
   - Calculate and record the digest of the complete observations file and the raw response evidence set.
   - The locked snapshot is immutable by protocol: evaluation reads the committed snapshot and must not rewrite it. A later observation requires a new experiment/run identifier and a new snapshot.
   - A filesystem read-only bit is only a convenience; integrity is established by committed content and verified hashes, not by file permissions alone.
   - Complete and verify the GT snapshot before any benchmark scoring begins.

4. **Model Input**
   - Baseline and JAMP must receive the exact same task records, prompt bytes, and raw LLM output.
   - The benchmark must not generate separate model responses for Baseline and JAMP.
   - Record prompt, model response, and task input hashes so paired-input identity can be checked mechanically.
   - The GT snapshot is not disclosed to either evaluator before its prediction is produced.

5. **Evaluation**
   - Evaluate the same locked task set with Baseline and JAMP.
   - Only tasks whose required Ground Truth is definitive (`EXISTS_ON_PYPI` or `NOT_FOUND_ON_PYPI`) are eligible for binary scoring.
   - `INCONCLUSIVE`, `AMBIGUOUS`, identity conflicts, malformed tasks, and missing paired predictions are excluded from binary metrics and reported explicitly with reasons.
   - Both systems' metrics must use the exact same paired-scored subset. Do not calculate Baseline and JAMP accuracy over different denominators.
   - No task may be removed after seeing model predictions to improve a result. Any exclusion rule must be applied deterministically and recorded.

## 3. Methodology Details

### 3.1 Real-package sample

- Use the official `hugovk/top-pypi-packages` dataset as the sampling frame, restricted to its first 1,000 ranked distributions.
- Pin the exact source revision and preserve the source snapshot used for the run. Record the repository commit, source file path, retrieval timestamp, and SHA-256 of the downloaded snapshot in the run manifest. Do not silently substitute a newer snapshot when reproducing a run.
- Treat the ranked list as ten consecutive rank strata: 1–100, 101–200, ..., 901–1000. Select exactly 10 candidates uniformly at random without replacement from each stratum, for 100 real-package candidates total.
- Use Python's `random.Random(42)` as the sole sampling PRNG. Process strata in ascending rank order and candidates in their source rank order before sampling. Record the seed, stratum boundaries, selected ranks, and selected normalized names in the manifest/evidence.
- This is a stratified random sample across the Top 1000 frame, not a claim of representativeness for all PyPI distributions. Candidate origin remains metadata and never determines Ground Truth.

### 3.2 Deterministic syntax-only Baseline

- The Baseline is a local, deterministic Python Standard Library implementation. It must not call PyPI, the network, an LLM, or any external API.
- Parse each paired task's exact source-code bytes with `ast.parse` and extract import statements from `ast.Import` and `ast.ImportFrom` nodes. Record the extracted import identifiers for auditability.
- If parsing succeeds and the task contains at least one target import, emit `CLEAN`. For binary scoring, `CLEAN` maps to the Baseline prediction **package exists / not hallucinated**. The Baseline does not attempt to establish whether an import resolves or whether its distribution exists.
- If parsing fails, or no target import can be extracted, emit an explicit invalid/unscorable result; do not classify it as `CLEAN` and do not count it as a correct or incorrect binary prediction. Apply this rule identically before inspecting Ground Truth or JAMP's prediction.
- This is intentionally a syntax-only negative-control baseline, not a general-purpose package validator. Its limitations must be stated beside every reported comparison.

### 3.3 Statistical uncertainty and paired comparison

- Calculate each system's accuracy on the exact same paired-scored subset. Report a two-sided 95% Wilson score confidence interval for each accuracy. Use `z = 1.959963984540054`; report the numerator, denominator, point estimate, and interval. If the scored denominator is zero, report accuracy and its interval as `null`.
- Compare JAMP and Baseline using the exact two-sided McNemar test on paired correctness outcomes. Let `b` be the number of pairs where JAMP is correct and Baseline is incorrect, and `c` the number where JAMP is incorrect and Baseline is correct. Report `b`, `c`, `b+c`, and the exact two-sided binomial p-value under `Binomial(b+c, 0.5)`. Use the exact test, not the asymptotic chi-square approximation.
- If `b+c = 0`, report that there are no discordant pairs and set the exact p-value to `1.0`; do not claim a measured advantage.
- Prespecify `alpha = 0.05` for the single primary paired comparison. Report the paired accuracy difference (JAMP minus Baseline) and discordant counts regardless of p-value. A p-value below 0.05 is evidence against equal error rates on this sample; it is not proof of general superiority or practical importance.
- Implement Wilson interval and exact McNemar calculations using Python Standard Library only. Do not add SciPy or other statistical dependencies. Preserve full precision in machine-readable results and round only for presentation.

## 4. Ground Truth Data Schema

Each observation is a JSON object in `observations.jsonl`:

```json
{
  "candidate_id": "uuid",
  "original_name": "string",
  "normalized_name": "string",
  "http_status": 200,
  "pypi_response_name": "string",
  "timestamp_utc": "ISO8601",
  "status": "EXISTS_ON_PYPI | NOT_FOUND_ON_PYPI | INCONCLUSIVE | AMBIGUOUS",
  "raw_response_sha256": "string"
}
```

Fields unavailable for a particular outcome must be represented as JSON `null`, not omitted or synthesized. For example, `http_status` and `pypi_response_name` may be null when no HTTP response was received. The raw-response digest is null only when no response body bytes were available.

The manifest must include at least:

- schema and benchmark version;
- experiment/run identifier;
- candidate generation method/version and seed, where applicable;
- candidate count and unique normalized candidate count;
- counts for each observed GT status;
- observation start/end timestamps;
- source endpoint and verification implementation version;
- observations-file SHA-256 and raw-evidence checksum-manifest SHA-256.

## 5. Metrics (Strict)

For binary metrics, define the positive class as **hallucinated package / package not found on PyPI**:

- **Accuracy:** `(TP + TN) / (TP + TN + FP + FN)`
- **Precision:** `TP / (TP + FP)`
- **Recall:** `TP / (TP + FN)`
- **Inconclusive Rate:** `unscored tasks / total attempted tasks`
- **Paired Accuracy Difference:** `JAMP Accuracy - Baseline Accuracy`, calculated over the same paired-scored subset.

Where a denominator is zero, report the metric as `null` / not defined; do not substitute zero or one.

Report the confusion matrix, scored count, unscored count by reason, and coverage alongside the metrics. The benchmark must not hide conflicts or inconclusive observations in aggregate accuracy.

No success thresholds are predefined. Report measured facts, sample size, and uncertainty; do not convert a small-sample result into a general performance claim.

Use only Python Standard Library modules for calculations (including `math` and `statistics`). Do not add SciPy or other heavy dependencies for this benchmark.

## 6. Definition of Done

- [ ] 200 unique candidates generated, with uniqueness checked after normalization.
- [ ] Independent GT verification completed for all candidates; all statuses and failures retained.
- [ ] GT Lock files and hashes committed before evaluation runs.
- [ ] The same 200 candidate/task inputs and exact same model outputs are processed by both systems.
- [ ] Baseline and JAMP are scored over the same paired subset.
- [ ] Inconclusive, ambiguous, conflicting, and unscored cases are explicitly reported.
- [ ] Evidence artifact contains manifest, observations, raw-response evidence/checksums, paired results, and metrics.
- [ ] Frozen Core invariant is verified: `src/jamp/run.py` remains at locked blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a` (`Δ = 0`).

## 7. Implementation Boundary

This PR is specification-only.

- No scripts are added in this stage.
- No runtime, router, Product Matrix, API, dependency, workflow, or test changes are authorized by this specification PR.
- `src/jamp/run.py` is strictly out of scope.
- Subsequent implementation is a separate stage and must follow this contract without weakening its evidence requirements.
