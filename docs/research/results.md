Established results. For raw evidence chains see
docs/methodology/finding-ledger.md (M-001..M-013).

## 1. Установлено экспериментально

Track A 30-run reproduction
  Result:   final_size = 13 in 30/30
            ROOTS=(2,3,5) × 5 seeds × 2 strategies
  Evidence: commit 4f5bbc47
            docs/replication/2026-09-12-track-a-experiment-reproduction.md
  Caveat:   isolated execution of frozen source, not canonical CI.
            Not expanded R_test.

Track A S0+ = 9
  Result:   AFTER_INIT = 6, AFTER_FIRST_CLOSURE = 9
            at d1b3a8c, root=2
  Evidence: commit d7e28e6
            docs/replication/2026-09-12-track-a-s0plus.md
  Caveat:   run() and substitution not performed.

## 2. Установлено формально (без execution)

H-J2 partial: C1 and C2 for current vocabulary
  Result:   source-closure (C1) and canon-stability (C2)
            established by code reading for vocabulary @ d1b3a8c
  Evidence: M-008
  Caveat:   branch-scope: current vocabulary only.
            General class characterization remains open.

H-J1 refined: branch-scoped substitution convergence
  Result:   substitution-layer has unique fixpoint for
            root=2, source p=2·k_6, vocabulary @ d1b3a8c
  Evidence: M-013
  Caveat:   evidence level = session-only.
            Not yet in repository.
            Cannot be cited as repository-artifact.

## 3. Negative results

H-P1: structural negative
  Result:   H-P1 formalization cannot be expressed in
            current JAMP vocabulary
  Evidence: M-011, Issue #40 comment 5646491353
  Level:    issue-comment
  Scope:    frozen vocabulary @ d1b3a8c

Extension cycle: negative
  Result:   no extension of current operator set yields
            paper-constructible positive control for
            state-dependent harness
  Evidence: Issue #39 (no separate M-record)
  Level:    issue-level
  Candidates E1/E2/E3 not certified.

## 4. Mixed (execution vs hypothesis)

P24-B
  Execution:   VERIFIED-SUCCESS
               run 34448469110, artifact digest
               sha256:957071bb...
  Hypothesis:  MIXED
               F1 lineage removal         FALSIFIED
               F2 causal-chain removal    FALSIFIED
               F3 verification removal    SUPPORTED
               F4 scoring removal         INCONCLUSIVE
               F5 calibration removal     FALSIFIED
  Evidence:    M-009
  Caveat:      execution success ≠ hypothesis confirmation.

## 5. Partial

P18.4
  Execution:   VERIFIED-PARTIAL
               run 34212659566, head_sha 7b717a8d (visual-merchant-hub)
               test file blob 910e1757
               1 failed, 139 passed
  Closed:      NO
  Cause:       baseline authorization fixture mismatch
               (ValueError instead of expected PermissionError)
  Caveat:      five P18.4 tests PASS-by-reconciliation,
               not direct per-test log evidence.
               Ablation observations lack valid baseline control;
               do not close causal claim.
  Next:        test-only correction + revalidation in
               visual-merchant-hub @ feature/p18-4-ablation-target
  Evidence:    M-010

## Non-claims

Not established by current repository evidence:
  - universal discovery capability
  - natural-language solving
  - general theorem proving
  - scheme generation
  - substitution convergence beyond current vocabulary
  - P18.4 as closed causal claim
