## Question
Why does `|closure(root)|` equal 13 across tested roots?

## Known
- 13 is not a `closure()`-only invariant.
- 13 emerges from `closure()` + substitution + target selection.
- Track A characterization is valid within its explicit scope (see #39).
- Characterization anchor: `d1b3a8c7e0cb6a16fb2eafacc5509382cecbcc39`, CI-unattested.

## Unknown
- whether 13 depends on operator-set structure;
- whether 13 depends on substitution rules;
- whether 13 depends on the initial axiom set;
- whether 13 generalizes beyond `R_test`.

## Required for progress
- EITHER an execution channel (see Task 5 in #39);
- OR a formal characterization of the substitution layer + target selection.

## Not in scope of this Issue
- re-running P1/P2;
- expanding `R_test`;
- modifying the operator set;
- Phase 3 resurrection.

This is a separate research cycle, not a continuation of #39.
