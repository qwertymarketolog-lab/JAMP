# P22.9 — Deterministic Hypothesis Scoring Contract

**Status:** Normative specification

**Baseline:** `9e514f8e7413de41fa6ad521a44e25628df7ebfb` (P22.8 LOCKED)

**Target:** `src/jamp/research/hypothesis_scoring.py`

This document defines the normative boundary for the P22.9 evaluation layer. P22.8 artifacts remain immutable.

## 1. Canonical-input determinism

The score MUST be a pure deterministic function of the canonical representation of the target hypothesis and its validated evidence/provenance graph. No hidden runtime state may participate.

## 2. Closed output domain

The aggregation function MUST map valid inputs into the closed interval `[0.0, 1.0]`:

`F: X -> [0.0, 1.0]`.

The numeric score is a structural **support score**, not a probability that the hypothesis is true.

## 3. Evidence grounding

A hypothesis with no valid evidence backing MUST NOT receive positive support. The zero-evidence baseline is `0.0` with an explicit zero-evidence provenance condition.

## 4. Evidence density (`D`)

`D` MUST be derived solely from canonically validated evidence records and their structurally admissible support paths. Raw record duplication MUST NOT increase density.

For a valid hypothesis with `n >= 1` unique evidence references, the normative density is:

`D = n / (n + 1)`.

This is a bounded, strictly increasing structural coverage measure and does not use global ledger size.

## 5. Independence (`I`)

`I` MUST be derived from graph structure, source identity, ancestry, and path dependence. Evidence duplicated through aliases or paths sharing a prohibited common causal ancestor MUST NOT be counted as independent support.

For the P22.9 initial implementation, admissible evidence references are independent only when their source hashes are distinct. Thus, for `n >= 1` references and `u` distinct source hashes:

`I = u / n`.

A single evidence reference therefore has `I = 1.0`; repeated support from the same source does not increase independence.

## 6. Cryptographic integrity (`C`)

`C` MUST be grounded in validated hashes and provenance links. Broken or tampered state/evidence/provenance hashes MUST cause structural invalidation and MUST NOT be converted into positive support.

For valid input, `C = 1.0`. Invalid cryptographic provenance raises a deterministic `ValueError` instead of producing a score.

## 7. Explicit aggregation

The normative aggregation is the equal-weight arithmetic mean:

`F(D,I,C) = (D + I + C) / 3`.

The coefficient for each component is exactly `1/3`. No hidden, learned, adaptive, or post-hoc weighting is permitted.

## 8. Structural monotonicity

For a verified independent evidence-path extension `ΔE`, with `L'_H = L_H + ΔE`, the contract requires:

`S(H,L'_H) >= S(H,L_H)`.

This property applies only where `ΔE` is independently verified and admissible under the same canonical rules. Under the fixed formula above, adding a new-source evidence reference increases `D` and leaves `I` unchanged at `1.0`, so the score cannot decrease.

## 9. Absolute serialization invariance

Equivalent canonical representations MUST yield identical scores. Dictionary insertion order, equivalent serialization order, and other non-semantic representation differences MUST NOT affect the result.

## 10. Environment invariance

The score MUST be invariant under changes to environment variables, system time, process identity, memory addresses, filesystem state, network state, and interpreter hash iteration behavior.

## 11. Cross-hypothesis non-interference

The score for `H1` MUST be independent of the presence, absence, identity, or score of every concurrent `H2`. No normalization against a global hypothesis pool is permitted.

## 12. Duplicate-reference handling

Duplicate evidence references are deterministically rejected with `ValueError`. They MUST NOT inflate support density.

## 13. Correlation and self-reinforcement control

Topologically dependent evidence paths MUST NOT be treated as independent merely because they have distinct surface identifiers. Circular, self-referential, or prohibited self-reinforcing support MUST be structurally invalidated or excluded according to deterministic graph rules.

The initial implementation rejects cyclic lineage graphs through `verify_lineage` and derives independence from distinct source identity; it does not infer independence from surface identifiers alone.

## 14. Read-only evaluation

Scoring MUST consume the evidence ledger and provenance graph without mutating them. The evaluation layer MUST NOT create, modify, delete, or feed records back into the Evidence Ledger.

## 15. No heuristic or probabilistic semantics

The score MUST NOT depend on model plausibility judgments, subjective confidence, Bayesian priors, learned parameters, arbitrary thresholds, ranking heuristics, fitness functions, or unrecorded expert weights. `0.87` means structural support under this contract, not an 87% truth probability.

## 16. Reproducible edge-condition semantics

All exceptional cases MUST have deterministic outcomes. At minimum:

| Scenario | Required behavior |
|---|---|
| Empty ledger | `0.0` plus explicit zero-evidence provenance status |
| Duplicate references | deterministic rejection; no density inflation |
| Broken/tampered hash | structural invalidation; deterministic `ValueError` |
| Correlated paths | independence component excludes prohibited dependent support |
| Invalid hypothesis provenance | scoring MUST NOT produce positive support |

## Mathematical acceptance properties

Before implementation is considered GREEN, the executable contract MUST establish at least:

1. **Determinism:** identical canonical input produces identical output.
2. **Boundedness:** every valid score lies in `[0,1]`.
3. **Monotonicity:** adding a verified independent support path cannot reduce score.
4. **Serialization invariance:** canonical-equivalent input has identical score.
5. **Environment invariance:** runtime/environment changes do not alter score.
6. **Non-interference:** adding unrelated hypotheses does not alter an existing score.
7. **Evidence dependence:** positive support requires valid evidence.
8. **Tamper sensitivity:** invalid cryptographic provenance cannot produce positive support.
9. **Read-only behavior:** scoring does not mutate evidence/provenance state.

## Implementation gate

The implementation is permitted only after the repository's active development instruction explicitly authorizes the transition from contract to production. P22.8 remains the immutable architectural baseline throughout P22.9.
