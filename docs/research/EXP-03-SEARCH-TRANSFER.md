# EXP-03 — Search Transfer

## Status

**SPECIFICATION ONLY — no implementation.**

This document defines the experiment before implementation. It does not claim that EXP-03 has been executed or that any of its outcomes are known.

## H3 — Hypothesis

**H3:** the existing Run v0.3 contract can execute a minimal branching/backtracking search if all search state, including the frontier, is stored in adapter-managed state, without changing `src/jamp/run.py`.

The target result is a real backtracking run, not merely a successful greedy path.

## Research question

Can the existing Run contract transfer from linear task execution to a search procedure that must explore one alternative, reach a dead end, return through the adapter-managed search state, and then explore another alternative — while keeping the Run implementation unchanged?

## Why 8-puzzle

EXP-02 already established a second-domain integration using the 8-puzzle. EXP-03 strengthens that domain rather than introducing a third domain.

The experiment will construct a minimal puzzle/search instance with a branching choice and a dead-end path such that the selected strategy must abandon the first alternative and continue with another one.

This is a test of the search abstraction boundary, not a claim that JAMP is a general 8-puzzle solver.

## Candidate definition

**`candidates(state)` returns frontier nodes.**

The strategy therefore selects which frontier node to expand next. This is the node-view of search and tests transfer of search policy (for example DFS/BFS/greedy), rather than selecting individual edges directly.

## Search-state definition

The adapter-owned state is the complete search state:

```text
SearchState = PuzzleState + Frontier + SearchBookkeeping
```

At minimum, the state must contain enough information to represent:

- the current puzzle/search position;
- frontier nodes available for expansion;
- visited/search bookkeeping needed to avoid invalid repeated exploration;
- any information required to continue after a dead end.

The exact representation is implementation-specific and is not part of the Run contract.

## Frontier ownership

The **adapter owns the frontier**.

The Run contract continues to see only its existing abstract interface:

```text
initial(state)
candidates(state)
admissible(state, candidate)
strategy(state, candidates)
apply(state, candidate)
terminal(state)
```

No frontier, queue, stack, visited-set, backtracking operation, or search-specific field is added to `src/jamp/run.py`.

The adapter-managed `state` may therefore represent substantially more than a single physical puzzle position. This is intentional: the experiment tests whether the existing state boundary is sufficient to carry search machinery without changing the Core.

## Required branching scenario

The experiment must contain a genuine branching situation of the following logical form:

```text
START
  |
  +--> A --> DEAD END
  |          |
  |          +--> BACKTRACK
  |
  +--> B --> GOAL
```

The strategy must first select the alternative leading to `A`, reach a state where that alternative cannot produce the goal, and then continue with `B`.

A run that simply follows a known successful path without abandoning an alternative is **not** sufficient for the target outcome.

## Required backtracking

Backtracking must be represented by the adapter-owned search state.

The Run loop itself must not gain a backtracking operation. A successful target execution therefore demonstrates that the adapter can encode the necessary frontier and search bookkeeping as ordinary state transitions:

```text
SearchState_0 → SearchState_1 → SearchState_2 → ...
```

The provenance of the Run remains a linear sequence of state transitions. The search tree, if any, exists inside the contents of those states rather than as a separate provenance topology.

## Terminal semantics

Terminal semantics are explicitly separated into three relevant outcomes:

1. **Goal found → `terminal`**
   - `terminal(state) == True` only when the goal has actually been reached.
2. **Frontier exhausted without goal → `exhausted`**
   - the search has no remaining frontier nodes;
   - the adapter must not report this condition as `terminal`.
3. **Budget exhausted → `budget`**
   - the Run budget is reached before either goal or successful exhaustion.

This distinction is required so that “search failed because there is nothing left to explore” cannot be confused with “search found the goal”.

## Core boundary

The following must remain unchanged during EXP-03:

- `src/jamp/run.py`;
- the Run v0.3 `RunResult` fields and semantics;
- the six-method Run/adapter boundary;
- the meaning of `steps`, `iterations`, and `stop_reason`.

A change to `src/jamp/run.py` required specifically to support branching/backtracking is a formal experimental result, not something to work around silently.

## Provenance requirement

The experiment must record enough provenance to establish, from the executed state sequence, that:

1. the initial search state was created;
2. a branching frontier existed;
3. the first alternative was selected;
4. that alternative reached a dead end;
5. the search state retained or recovered an alternative;
6. the second alternative was selected;
7. the goal was reached, or the search was correctly classified as exhausted/budget.

The provenance representation remains opaque to Artifact v0.

The experiment must **not** assume that provenance itself becomes a tree. The primary question is whether the linear sequence of `SearchState` transitions is sufficient to carry and expose the branching search process.

## Outcome classification

### A — Weak PASS

The existing Run contract executes a successful greedy search, but the experiment does not demonstrate genuine abandonment of one alternative followed by exploration of another.

Classification: **technical PASS of execution, insufficient for the target EXP-03 claim.**

### B — TARGET PASS

The existing Run contract executes a genuine branching/backtracking search using adapter-owned `SearchState`, including frontier and search bookkeeping, with no changes to `src/jamp/run.py` or `RunResult`.

This is the required successful outcome of EXP-03.

### C — FAIL-1: Core abstraction too narrow

The required search cannot be expressed without adding a search-specific field or method to the Run contract itself, for example a frontier/backtracking API in `src/jamp/run.py`.

This is a valid and valuable architectural result. It means the current Core boundary is insufficient for this class of search.

## Artifact / viewer outcomes

Artifact behavior is evaluated independently of the Core result.

### Artifact PASS

If the existing Artifact v0 can carry the executed search result using the existing typed metadata plus opaque `final_state` and `provenance`, with no domain-specific Artifact schema change, the artifact layer passes this part of the experiment.

The fact that the search tree lives inside `SearchState` means Artifact v0 does not need a tree-shaped provenance contract merely to preserve the execution.

### D — Search Core PASS, viewer requires domain-aware reconstruction

If the Core and Artifact v0 can preserve the linear `SearchState` transition sequence, but the viewer cannot meaningfully display the search structure without domain-aware logic that reconstructs the tree from `SearchState`, classify this separately as:

**D — Search Core PASS, viewer requires domain-aware reconstruction.**

D is not a Core failure. It is a viewer/domain-boundary finding.

If the viewer can show the relevant search sequence without domain-specific reconstruction, no D finding is required.

## Additional failure conditions

The following are separate from C and must not be silently folded into it:

- **RunResult failure:** the search requires new domain-specific fields or altered RunResult semantics to communicate its result.
- **Artifact failure:** the required executed result cannot be represented by Artifact v0 without domain-specific schema/serializer changes.
- **Reproducibility failure:** the required branching/backtracking behavior cannot be deterministically demonstrated from a fixed initial condition and declared execution parameters.

These findings must be reported separately if encountered.

## Evidence requirements

A completed EXP-03 report must include:

1. the exact execution commit SHA;
2. confirmation that `src/jamp/run.py` was unchanged at execution;
3. the exact test/execution command;
4. observed `steps`, `iterations`, and `stop_reason`;
5. evidence of the branching scenario and actual backtracking;
6. the final search state and its declared interpretation;
7. the serialized Artifact v0 result, if artifact testing is included;
8. provenance sufficient to distinguish the first failed alternative from the successful alternative;
9. working-tree cleanliness or an explicit explanation of any deviation.

## Final-state semantics

`final_state` semantics are intentionally **not fixed by this specification**.

Two possible interpretations remain open:

- the complete adapter-owned `SearchState`, including frontier and visited/search bookkeeping;
- the goal path / task-level final state.

EXP-03 may provide evidence relevant to this design choice, but neither interpretation is claimed as the Artifact v0 contract in advance.

## Not claimed

EXP-03 does **not** claim:

- that backtracking in one 8-puzzle instance represents backtracking in general search;
- that DFS, BFS, greedy search, or another search policy is universally supported;
- that the choice of DFS versus BFS is irrelevant to the experiment outcome;
- that a greedy success is equivalent to the target backtracking result;
- that provenance has a tree structure;
- that Artifact v0 defines a canonical or minimal search schema;
- that Artifact v0 is stable across future Run contract versions;
- that `final_state` semantics have already been selected;
- that the viewer is domain-neutral merely because Artifact v0 is opaque;
- that JAMP is a general-purpose search solver;
- that EXP-03 has been executed.

## Stop condition for implementation planning

No implementation should begin until this specification is treated as the fixed experimental protocol.

The first implementation question is not “how to make the puzzle pass”, but whether the existing Run v0.3 boundary can express the required search without modification.
