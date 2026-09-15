# BOUNDARIES.md — JAMP v0.x Structural Limitations and Negative Results

> **Status:** Snapshot as of 2026-09-15
>
> **Snapshot commit:** `c461ed50e55f89e06c93f0ca815713ece9bd0cdf`
>
> **Expected revision:** review after Experiment #2
>
> **Core principle:** A negative result or structural limitation is a research output that defines the observed boundary of the current mechanism. It is not, by itself, a project failure.

## Scope

This document records structural boundaries supported by the current repository evidence and the audited research record. It does **not** claim that these domains are impossible in principle for a future system. It describes what JAMP v0.x has and has not demonstrated.

The current `main` branch contains the isolated Track A symbolic experiment under `track_a/`. The repository status explicitly does not claim universal discovery, natural-language solving, general theorem proving, scheme generation, or substitution convergence beyond the current vocabulary.

## 1. Domain gap / expressible-class boundary

**Boundary:** the current Track A state representation and vocabulary do not natively represent arbitrary external problem domains.

**Observed evidence:** Track A uses a finite symbolic expression representation (`E`) with operations such as equality, divisibility, multiplication, powers, predicates, `gcd`, and a contradiction marker. Its execution is specialized to that vocabulary and to the numeric-root construction in `track_a/common.py`.

**Open-domain examples:** H-P1 and the Riemann Hypothesis are outside the demonstrated expressible class. H-P1 is recorded as a structural negative in the repository research record; the Riemann Hypothesis has not been implemented as a Track A artifact.

**Not claimed:** JAMP cannot reason about other domains in principle. Only that such transfer has not been demonstrated by the current mechanism.

## 2. Rule gap

**Boundary:** the current rewriting / inference vocabulary does not establish general algebraic closure.

**Observed evidence:** Track A relies on a specific finite rule set (`derive_divisibility`, `prime_square_lemma`, `divisibility_witness`, `integer_witness`, and `gcd_contradiction`) together with substitution routing. The reproduction record shows a bounded experiment in which all 30 runs stopped at `MAX_ITERATIONS` with `solved = false`; this is evidence about that frozen rule/search configuration, not a theorem about all possible algebraic systems.

**Extension-cycle evidence:** the audited extension cycle did not produce a certified positive control for the state-dependent harness. This remains a boundary of the tested rule/extension configuration.

## 3. Extension gap

**Boundary:** extending a local validation mechanism to a broader claim can lose formal strictness or require assumptions not established by the existing evidence.

**Observed evidence:** H-P1 is recorded as a structural negative: its formalization cannot be expressed in the current JAMP vocabulary. The repository research record also records the extension cycle as negative and does not certify the candidate E1/E2/E3 controls.

**Interpretation:** this is a boundary of the tested mechanism and evidence chain, not a claim that broader validation is impossible in a future architecture.

## 4. No-producer

**Boundary:** an architectural behavior cannot be treated as a system-wide mechanism merely because one local producer exhibits it.

**Observed evidence:** provenance-producer audits of `derivation.py`, `composition.py`, and `p17/closed_loop.py` found total-preserving provenance behavior rather than a second independent producer of filtered selective causality. No second producer has been established for the hypothesized behavior.

**Consequence:** a local producer is not promoted to a global architecture rule without an independent producer and evidence.

## 5. Single-case-only

**Boundary:** a locally observed invariant remains local until an independent second producer or case establishes a broader invariant.

**Observed evidence:** the MSC / O_4 selection behavior is localized to O_4. The search for a second independent producer returned null, and the proposed global invariant was rejected (ADR-0004 discarded).

**Reachability note:** the same discipline applies to open-problem claims: the current repository evidence does not establish a general open-problem solving capability. The reachable class is bounded by the expressions and rules actually represented and executed.

## Evidence posture

The repository evidence distinguishes execution from inference:

- Track A 30-run reproduction: `30/30` runs reached `final_size = 13`, `solved = false`, `stop_reason = MAX_ITERATIONS` under the frozen 2026-09-12 parameterization.
- H-P1: structural negative, recorded in the research results / finding ledger.
- Universal discovery, natural-language solving, general theorem proving, scheme generation, and substitution convergence beyond the current vocabulary are explicitly **not established**.

## What this document does not say

It does not say that JAMP is permanently limited to Track A, nor that a second domain cannot work. It says that such a transfer is currently a hypothesis and must be tested as a separate experiment.

This snapshot is expected to change when Experiment #2 produces new evidence.
