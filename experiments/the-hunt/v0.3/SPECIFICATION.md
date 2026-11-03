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
  - For packages: Human-verified or Web-search verified via PyPI.
  - For APIs: Automated introspection using Python's `inspect` module against the *actual* installed package version.

## 3. JAMP v0.3 Engine Components
### A. Provenance Analysis
JAMP will query PyPI metadata and calculate a "Trust Score":
- **Age:** < 30 days (High Risk), < 1 year (Medium), > 1 year (Low).
- **Downloads:** < 100 (High Risk), < 10,000 (Medium), > 10,000 (Low).
- **Author/Repo:** Missing repository link (High Risk).

### B. Signature Verification
- Extract AST calls (e.g., `requests.get_secure_data()`).
- Dynamically import the real library (in a sandbox).
- Use `inspect` to check if the method exists. If `AttributeError`, JAMP blocks it as `INVALID_SIGNATURE`.

## 4. Baseline vs JAMP
- **Baseline:** AST syntax check + simple PyPI existence check (v0.2 logic).
- **JAMP:** AST + PyPI existence + Provenance Trust Score + Signature Verification.

## 5. Definition of Done
- [ ] Real LLM outputs generated and saved.
- [ ] Provenance checks implemented (age, downloads).
- [ ] Signature checks implemented via `inspect`.
- [ ] Paired evaluation (Baseline vs JAMP) with McNemar test.
- [ ] Evidence artifact with raw PyPI metadata and signature validation logs.
