# Reachable open-problem audit

**Question:** Does there exist an open mathematical problem that can be formulated completely inside the current Track A ruleset, without adding operators or rules?

**Scope:** `track_a/common.py @ 4b60fb890fb171494dcab1c8b2ca67b5dd0a56ba` on branch `o4-tighten-v01`.

## Current Track A vocabulary

The implementation provides a generic AST node `E` and therefore can syntactically carry arbitrary operator labels. The active rule set, however, recognizes only the following mathematical forms:

- equality `=`
- divisibility `|`
- power `^`
- multiplication `*`
- `gcd`
- predicates `prime`, `integer`
- order `>`

The existing closure rules operate on these forms: square/divisibility derivation, the prime-square lemma, divisibility witnesses, integer witnesses, and the gcd contradiction rule.

The important boundary is therefore **rule-level**, not AST-type-level: an operator such as `/`, `%`, or `+` could be stored syntactically, but there is no current Track A rule that gives it mathematical behavior.

## Candidate audit

A bounded inspection was made against representative currently open integer/number-theory problems and problem families whose statements are close to the available vocabulary.

| Candidate | Current status | Missing from Track A | Classification |
|---|---|---|---|
| Collatz conjecture | open | `+`, `/` or equivalent halving, parity/conditional rule, termination predicate | rule-negative |
| Twin Prime Conjecture | open | addition / fixed difference and prime condition on the transformed value | rule-negative |
| Goldbach-type problems | open | addition of primes | rule-negative |
| Legendre-type prime-gap problems | open | addition/order interval construction | rule-negative |
| Odd perfect number problem | open | divisor-sum / aggregation operation | rule-negative |
| Mersenne-prime infinitude | open | subtraction (`2^p - 1`) and the resulting primality construction | rule-negative |
| Wieferich-prime infinitude | open | subtraction/congruence/modular relation (`2^(p-1)-1` modulo `p²`) | rule-negative |
| Erdős–Moser conjecture | open | addition/summation over a sequence | rule-negative |
| Powerful-product / consecutive-integer problems | open | consecutive-number construction and multiplication over a variable-length sequence | rule-negative |

The external status of these examples was checked against current open-problem sources. For example, current sources still list the Twin Prime, Legendre, and odd-perfect-number questions as open; Mersenne-prime infinitude remains open; Wieferich-prime infinitude remains open; and the Erdős–Moser equation remains unresolved. The recent Erdős problem concerning powerful products of consecutive integers is also recorded as open.

## Result

**No suitable open problem was found inside the current Track A ruleset.**

This is a **bounded negative result**, not a mathematical proof that no such problem exists anywhere in mathematics.

The inspection found a recurring structural boundary: interesting open integer problems can get close to the current language through `prime`, `integer`, `|`, `^`, `*`, and `gcd`, but their actual conjectural content requires at least one missing operation or rule such as addition, subtraction, modular arithmetic, parity/branching, sequence aggregation, or a termination/quantifier mechanism.

The three previously inspected examples now have a consistent interpretation:

- H-P1: **domain-negative** — the required mathematical object class is absent.
- Riemann Hypothesis: **domain-negative** — complex/analytic structure is absent.
- Collatz: **rule-negative** — the integer-expression domain is present, but the required rules are absent.
- This audit: **no reachable open problem found** within the current Track A rule boundary.

## What is not claimed

- This does **not** prove that JAMP as a system cannot address an open mathematical problem.
- This does **not** justify adding operators or rules merely to make a selected problem executable.
- This does **not** turn Collatz, Riemann, or another problem into a JAMP target.
- This does **not** constitute an exhaustive survey of all open mathematics.

## Consequence for the research program

The current ruleset has reached a genuine external-input boundary: no externally interesting open problem was identified that is both nontrivial and expressible without extending the rule vocabulary.

Therefore the next JUMP should **not** be invented internally. A future extension must be motivated by a new external observation/question and then audited as a new vocabulary/ruleset experiment.

## Sources checked

- Current open-problem archive: UnsolvedMath, open mathematics problem list.
- Mersenne primes: UnsolvedMath problem record, current literature triage.
- Wieferich primes: ScienceDirect overview and OEIS A001220.
- Erdős–Moser: TheoremDB current open record.
- Powerful numbers in products of consecutive integers: TheoremDB Erdős Problem 137.

Inspection date: 2026-09-15.
No runtime execution was performed for this audit; this is a source/code inspection result only.
