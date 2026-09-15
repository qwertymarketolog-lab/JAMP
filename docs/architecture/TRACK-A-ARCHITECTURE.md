# Track A Architecture — JAMP v0.x

> **Status:** repository snapshot / descriptive record
>
> **Source snapshot inspected:** `c461ed50e55f89e06c93f0ca815713ece9bd0cdf`
>
> **Documentation commit:** created after the source snapshot; this document is expected to be revised if the Run v0.3/exporter/viewer contour is added to or identified in another repository ref.

## 1. Scope

This document describes the Track A implementation that is actually present in the inspected `main` tree. It does not promote the Track A experiment into a universal search engine and does not infer capabilities that are not represented by source artifacts.

The current Track A implementation is an isolated symbolic experiment. `track_a/common.py` describes it as a self-contained symbolic engine with no JAMP-Delta phases, MCTS, learned policy, or root-specific shortcuts. Baseline and treatment differ in substitution routing while sharing the other rules and boundaries.

## 2. Repository contour

```text
track_a/common.py
        │
        ├── symbolic expression type E
        ├── canonicalization
        ├── State
        ├── closure rules
        ├── substitution generation
        └── run(...)
        │
        ├──────────────┐
        ▼              ▼
baseline_random   treatment_targeted
        │              │
        └──────┬───────┘
               ▼
        track_a/experiment.py
               │
               ▼
          result records
```

The repository also contains `track_a/results/` for experiment results and the replication record under `docs/replication/`.

## 3. State representation

`track_a/common.py` defines a frozen expression node `E` with:

- `num` and `var` leaves;
- operators including `=`, `|`, `^`, `*`, `gcd`, `prime`, `integer`, and `>`;
- a contradiction marker represented as an expression operation.

The initial `State` is constructed from a numeric root and contains the anchor relation, prime/integer axioms, a `root > 1` condition, and a `gcd(p,q,1)` condition.

The state maintains:

- `objects`;
- a canonical-expression index;
- `history`;
- maximum expression depth observed;
- a solved flag;
- a maximum-object bound (default `120`).

## 4. Transformation / closure rules

The current closure implementation contains a small fixed vocabulary of transformations, including:

- `derive_divisibility`;
- `prime_square_lemma`;
- `divisibility_witness`;
- `integer_witness`;
- `gcd_contradiction`.

Canonicalization performs limited simplifications and a specific square/divisibility normalization. Substitution is generated either by the baseline random routing or by the treatment targeted routing.

This vocabulary is the object of the experiment. It is not a claim of general algebraic closure.

## 5. Search / execution

`run(seed, root, strategy, N=200, max_objects=120)` constructs the state, performs closure, then repeatedly chooses a substitution candidate according to the selected strategy and applies closure again.

The current implementation returns a plain result mapping containing:

- root;
- seed;
- strategy;
- solved;
- steps;
- progress;
- max_objects;
- ast_depth;
- stop_reason;
- trace.

The `steps` field in this implementation is `len(s.history)`. `history` records inserted objects, including initial anchor/axiom entries. Therefore `steps` is not equivalent to a generic count of strategy `apply` calls unless that equivalence is separately demonstrated.

## 6. Provenance / trace

Each successful `State.add(...)` appends a history record containing:

```text
step
op
parents
expr
```

The parent indices identify the source objects used by that transformation. This is the concrete provenance available in the Track A experiment source.

The history is therefore an experiment trace, not a general-purpose provenance DAG abstraction. No broader claim is made here.

## 7. Terminal states

The current Track A runner returns:

- `SOLVED` when the contradiction marker is reached;
- `MAX_OBJECTS` when the object bound is reached without solving;
- `MAX_ITERATIONS` otherwise after the configured iteration budget is exhausted.

The 2026-09-12 reproduction reports all 30 frozen runs as:

```text
solved      = false
steps       = 13
progress    = 7
final_size  = 13
ast_depth   = 9
stop_reason = MAX_ITERATIONS
```

That result is an empirical result of the frozen parameterization. It is not by itself a proof that `13` is a universal invariant.

## 8. Reproduction evidence

The repository replication record identifies:

- anchor: `d1b3a8c7e0cb6a16fb2eafacc5509382cecbcc39`;
- `track_a/common.py`: `d0956421f54e76a89f4a845e306f30f7b1d3c8e8`;
- `track_a/experiment.py`: `c6ca39e2ada1e5e74c124b2326cac17596ec5f12`;
- parameterization: `ROOTS=(2,3,5)`, `SEEDS=(0,1,2,42,99)`, `N=200`, `max_objects=120`, two strategies;
- result: 30/30 stopped at `MAX_ITERATIONS`, 0/30 solved.

The replication record explicitly describes this as isolated execution of frozen source rather than canonical CI reproduction.

## 9. Evidence boundary: Run v0.3 / exporter / viewer

The broader contour discussed during the 2026-09-15 planning session was:

```text
Track A → Run v0.3 → JSON exporter → run_result.json → Viewer
```

The inspected `main` tree at source snapshot `c461ed50...` does **not** contain a `src/jamp/run.py`, a `RunResult` implementation matching that description, or an identified `run_result.json` / viewer implementation. Therefore this architecture record deliberately does **not** claim that contour as a repository fact.

If that contour exists on another ref or in an unmerged worktree, it must be identified by exact ref/path before this document is extended with those claims.

## 10. D1–D8 divergence

The planned architecture record calls for documentation of the D1–D8 distinction between Track A step/history counts and a RunResult apply-call count. The inspected `main` source establishes the Track A side (`steps = len(history)`) but does not contain the referenced RunResult implementation. Consequently the full D1–D8 comparison is **not asserted here** until the corresponding RunResult source is identified.

This is intentional: the architecture document must not convert a session-level description into an unsupported repository claim.

## 11. Equivalence gate

The architecture should reference the existing equivalence result when the exact repository path is present. The current inspected tree did not expose a file named `docs/run/track-a-adapter-equivalence-result.md` through the main-tree inspection used for this snapshot. Therefore no PASS count is repeated here without a repository path that can be verified.

## 12. Reproducibility status

**Verified by local/isolated execution of the frozen Track A source as recorded in the repository replication artifact. Independent reproduction through this repository's canonical CI configuration is not demonstrated by that artifact.**

This statement is deliberately narrower than a general claim of reproducibility.

## 13. Non-claims

This Track A architecture does not establish:

- a domain-agnostic search engine;
- a general adapter interface;
- universal problem solving;
- natural-language problem ingestion;
- general theorem proving;
- a generic verification engine;
- a universal provenance DAG;
- transfer to programming, business, data, science, or other domains.

Those are future hypotheses or separate experiments, not properties of the current Track A implementation.
