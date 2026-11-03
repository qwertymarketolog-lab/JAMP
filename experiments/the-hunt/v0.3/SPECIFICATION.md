# The Hunt Benchmark v0.3 — Provenance & Signatures

## 1. Objective
To measure JAMP's ability to detect **sophisticated hallucinations**:
- Slopsquatting (fake packages that *do* exist in PyPI but have malicious/untrustworthy provenance).
- Fake APIs (calling non-existent methods on real libraries).
- Real LLM hallucinations (moving away from synthetic inputs).

## 2. Dataset Requirements (Real LLM)
- **Source:** OpenRouter API (Model: `openai/gpt-4o-mini` or similar).
- **Tasks:** 100 prompts designed to induce hallucinations (e.g., asking for obscure integrations).
- **Ground Truth:**
  - For packages: Human-verified or Web-search verified against PyPI, with the source and observation time retained.
  - For APIs: Static analysis of the exact downloaded wheel version using Python's `ast` module. No package installation or import is permitted.

## 3. JAMP v0.3 Engine Components

### A. Provenance Analysis
JAMP queries PyPI JSON metadata and calculates a deterministic Trust Score, starting at 100 points.

**First-publication age**
- Derive the first publication timestamp from the earliest available release-file `upload_time` in the PyPI `releases` data.
- Calculate elapsed age against the UTC observation timestamp.
- Age penalty: less than 30 days: **−50**; at least 30 days but less than 365 days: **−20**; at least 365 days: **0**.
- If no usable release timestamp exists, provenance is **INCONCLUSIVE**; do not infer a safe age.

**Repository**
- A GitHub or GitLab repository URL in PyPI `project_urls`: **0** penalty.
- No such repository URL: **−30**.

**Author**
- A non-empty `author` or `author_email` field: **0** penalty.
- Both fields empty or missing: **−20**.

**Score and decision**
- `trust_score = max(0, 100 - age_penalty - repository_penalty - author_penalty)`, where penalties are positive magnitudes as listed above.
- A score **below 50** produces `PROVENANCE_SUSPICIOUS` and blocks the package.
- A score of exactly 50 or higher does not trigger this threshold by itself; other JAMP gates still apply.
- Preserve the raw PyPI response, UTC observation timestamp, derived first-publication timestamp, individual penalties, and final score in the evidence artifact.

### B. Signature Verification
- Extract candidate module, class, and function calls from the generated code's AST.
- Download the exact package wheel (`.whl`) from the PyPI release metadata; do not install the package and do not execute package code.
- Inspect the wheel as an archive and read relevant `.py` source files directly. Reject archive paths that escape the extraction/read boundary; do not extract files to an executable environment.
- Parse source text with `ast.parse` and statically inspect module, class, and function definitions to determine whether the referenced API symbol is declared.
- If the referenced symbol is absent from the statically inspectable source, block it as `INVALID_SIGNATURE`. If the wheel, module mapping, or source cannot be resolved conclusively (including extension-only or dynamically generated APIs), return `INCONCLUSIVE`, not a false `INVALID_SIGNATURE` or PASS.
- No `import`, `importlib`, package installation, or `inspect` call against the downloaded package is permitted.

**Security and interpretation limits:** AST parsing does not execute the parsed source, but static presence is not proof that a call will work at runtime. It may not resolve dynamic attributes, generated APIs, compiled extensions, or environment-dependent behavior. These cases must remain `INCONCLUSIVE` unless separately verified by an independently designed safe method.

## 4. Implementation Details (Security & Determinism)
1. **Download statistics are excluded from v0.3 scoring.** The standard PyPI JSON API does not provide download counts. The age signal is derived only from the earliest available release-file `upload_time` in `releases`; no substitute or inferred download metric may be used.
2. **Trust Score is deterministic.** Apply the age, repository, and author penalties defined in Section 3A to a starting score of 100, clamp the result at zero, and block only when the resulting score is below 50. Missing first-publication evidence is `INCONCLUSIVE`, not a zero-age or low-risk assumption.
3. **Signature checks are static-only.** Read `.py` source from the exact PyPI wheel without installation or import, parse it with `ast.parse`, and inspect declarations. Never execute untrusted package code in the GitHub Actions runner. Missing or non-statically-resolvable symbols are handled as specified in Section 3B.

## 5. Baseline vs JAMP
- **Baseline:** AST syntax check + simple PyPI existence check (v0.2 logic).
- **JAMP:** AST + PyPI existence + Provenance Trust Score + static Signature Verification.

## 6. Definition of Done
- [ ] Real LLM outputs generated and saved.
- [ ] Provenance checks implemented (first-publication age, repository, author).
- [ ] Deterministic Trust Score and `PROVENANCE_SUSPICIOUS` threshold implemented.
- [ ] Static signature checks implemented using wheel source and `ast.parse`, without installation or execution.
- [ ] Paired evaluation (Baseline vs JAMP) with McNemar test.
- [ ] Evidence artifact with raw PyPI metadata, scoring inputs, and signature validation logs.
