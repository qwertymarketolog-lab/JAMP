# EXP-03 — Execution Evidence

## Status

**B — TARGET PASS**

EXP-03 demonstrates that the existing Run v0.3 boundary can execute the required minimal branching/backtracking search without changes to `src/jamp/run.py` or `RunResult`.

This evidence record is separate from the fixed experimental protocol in `EXP-03-SEARCH-TRANSFER.md`.

## Execution anchor

- Commit: `7e8714e4af6bf0179231a295304ce50ed635cb6d`
- Core file: `src/jamp/run.py`
- Core blob at the execution anchor: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`
- Test command:

```text
PYTHONPATH=src:. python -m pytest -q tests/research/test_exp03_search_transfer.py
```

- Reported execution result: `2 passed in 0.68s`
- Working tree: clean at the successful execution anchor.

The successful test execution was performed locally and reported in the research session. The GitHub repository records the exact commit and test implementation; the execution result itself is not claimed as a GitHub Actions run.

## Protocol correspondence

### Fixed graph

```text
X = 0
A = 1
B = 2
S = 3
G = 4

S -> A
S -> B
A -> X
B -> G
```

The implementation uses exactly this graph and fixed node IDs.

### Deterministic selection

The adapter strategy is `min(cands)`. Therefore the observed selected sequence is:

```text
S -> A -> X -> B -> G
```

The test asserts the same sequence in both the exported provenance and the adapter history.

### Run result

The successful execution asserts:

```text
steps      = 5
iterations = 5
stop       = terminal
```

The adapter budget is `10`, so the successful run terminates before budget exhaustion.

### Core boundary

`src/jamp/run.py` is unchanged at blob SHA:

```text
0fee0e1c5c1a1548361965ac51eacdeba62bfe8a
```

The test explicitly obtains `HEAD:src/jamp/run.py` and compares it with this expected SHA. No frontier, queue, stack, or backtracking API was added to Core.

## Backtracking semantics

EXP-03 does **not** implement a `backtrack()` Core action.

The adapter owns the complete search state, including the frontier. After `S` is expanded, the frontier contains `A` and `B`. The minimum-ID strategy selects `A`. After `A`, the frontier contains `B` and `X`; `X` is selected next. Expanding `X` produces no successor, but `B` remains in the frontier.

The next ordinary Run iteration selects `B`, then `G`.

Therefore the experimentally demonstrated backtracking mechanism is:

```text
A -> X -> dead end
       |
       +-- pending B retained in adapter frontier
              |
              v
              B -> G
```

This is **frontier fallback**, not an explicit rollback operation and not a new Run event. The Core observes only successive immutable `SearchState` transitions.

## Provenance

The adapter records a linear history of `(before, selected, after)` state transitions. The test asserts:

- history length equals `steps`;
- selected IDs are `3, 1, 0, 2, 4`;
- every `after` state equals the next transition's `before` state.

The exported provenance additionally establishes:

```text
selected: S
selected: A
selected: X
  after X: frontier = [B]
selected: B
  after B: frontier = [G]
selected: G
```

Thus the evidence distinguishes the dead-end `A -> X` branch from the successful `B -> G` continuation without requiring tree-shaped Core provenance.

## Artifact v0

The EXP-03 exporter calls the existing neutral `serialize_run_result()` from `scripts/artifact_v0.py`.

No Artifact v0 schema or serializer change was made for EXP-03.

The artifact contains the existing typed Run result fields:

```text
artifact_version
adapter
run_result.steps
run_result.iterations
run_result.stop_reason.kind
run_result.stop_reason.detail
```

plus opaque domain payloads:

```text
final_state
provenance
```

For EXP-03 the final-state payload is JSON-safe and contains:

```text
current
frontier
visited
```

The test performs a JSON serialization/deserialization round-trip and asserts equality with the original artifact.

### Artifact result

**Artifact PASS.**

The existing Artifact v0 shape carries the executed search result without a domain-specific schema extension. The search structure remains encoded inside the opaque domain payloads rather than being imposed on Artifact v0.

## Final state

The expansion model reaches the goal only after `G` is selected and applied. The resulting visited sequence is:

```text
[S, A, X, B, G]
```

The final frontier is empty after `G` is expanded. The test explicitly asserts that `G` is visited and that the visited sequence equals the required path.

This is evidence for EXP-03; it does not redefine the general Artifact v0 `final_state` contract.

## Outcome classification

### B — TARGET PASS

All target conditions are satisfied by the implementation and the reported successful execution:

- genuine branching exists;
- `A` is selected before `B`;
- `X` is reached as a dead end;
- the Run does not terminate at `X`;
- `B` remains in adapter-owned frontier state;
- `B` is subsequently selected;
- `G` is reached and causes terminal stop;
- `steps = 5`;
- `iterations = 5`;
- budget = `10`;
- `src/jamp/run.py` remains unchanged;
- `RunResult` remains unchanged;
- provenance remains a linear state-transition chain;
- Artifact v0 carries the result without schema changes;
- JSON round-trip succeeds.

## What EXP-03 actually establishes

EXP-03 establishes a narrower result than “JAMP now has general search”.

It demonstrates that the current Run state boundary is sufficient to host this minimal branching/backtracking mechanism when the adapter owns the frontier and search bookkeeping.

The experiment does **not** establish general DFS, BFS, A*, arbitrary graph search, universal backtracking, or a domain-neutral search viewer.

## Research conclusion

**The current Core boundary is not the limiting factor for this minimal branching case.** Search state can be carried through ordinary immutable adapter state, and the required alternative can survive a dead-end without adding a Core backtracking primitive.

The next architectural question is therefore not “add backtracking to Run”, but whether this pattern remains valid under a materially broader search workload. No such generalization is claimed by EXP-03 itself.
