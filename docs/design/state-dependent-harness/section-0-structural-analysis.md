# Section 0 — Structural Analysis

**Date:** 2026-09-11  
**Status:** COMPLETE / NEGATIVE  
**Design:** State-Dependent Harness  
**Anchor:** `49a5c86be320cab5f998001182e6a3ffa836ec1c`  
**Root:** `2`  
**Phase 3:** BLOCKED — structurally rejected before execution

## 1. Purpose

Section 0 tests whether the current JAMP operator set can support a genuine path-dependent gate before any Phase 3 traversal is executed.

The question is not whether two schedules can produce different step counts. The question is whether there exists a gated rule `R` whose activation is absent at `S0+` and whose activation/state exposure can differ between traversals within the same budget.

Define:

`Novelty(R) := not Trigger_R(S0+)`

`PathDependence(R) := exists S*: Trigger_R(S*) and S* is reachable within the fixed budget by one valid traversal but not by every valid traversal.`

The required structural condition is:

`exists R: Novelty(R) AND PathDependence(R)`.

If no such `R` exists, the state-dependent harness is structurally inapplicable to the current operator set and Phase 3 MUST NOT be executed.

## 2. Keystone assumption

The keystone property is that substitution preserves its source equality. The substitution operation creates a new canonical expression but does not consume, remove, or invalidate the source equality from `State.objects`.

In the anchor implementation, `State.add()` only appends new expressions when absent; the substitution functions construct `T(new, op, parents)` and do not delete or deactivate the source. The source therefore remains available after a successful substitution.

This property is the basis for the commutative-accumulation argument. If JAMP later changes substitution so that a source can be consumed or invalidated, this Section 0 result MUST be reconsidered.

Reference implementation: `track_a/common.py`, anchor `49a5c86be320cab5f998001182e6a3ffa836ec1c`.

## 3. S0+ baseline

After the initial `closure()` on root `2`, the state contains nine canonical objects:

1. `p^2 = 2*q^2`
2. `prime(2)`
3. `integer(p)`
4. `integer(q)`
5. `2 > 1`
6. `gcd(p,q,1)`
7. `2 | p`
8. `p = 2*k_6`
9. `integer(k_6)`

The only source equality with a variable on the left is `p = 2*k_6`.

## 4. Gated-rule audit

| Rule | Trigger predicate | Novelty at S0+ | Path-dependence | Result |
|---|---|---:|---:|---|
| `derive_divisibility` | `a^2 = d*b^2`, numeric `d` | NO | — | excluded |
| `prime_square_lemma` | `d|x^2` AND `prime(d)` AND `integer(x)` | YES | NO | excluded |
| `divisibility_witness` | numeric `d|variable x` | NO | — | excluded |
| `integer_witness` | same `d|x` witness path | NO | — | excluded |
| `gcd_contradiction` | `root|p` AND `root|q` AND `gcd(p,q,1)` | YES | NO | excluded |

### 4.1 derive_divisibility

The trigger is already satisfied by the initial equality `p^2 = 2*q^2`. Therefore it is not novel at `S0+`.

### 4.2 prime_square_lemma

The rule requires a state containing `d|x^2`, `prime(d)`, and `integer(x)`. Root-2 `S0+` contains `prime(2)` and `integer(p)`, but does not contain the required `2|p^2` trigger. The current closure/substitution system does not provide a path-dependent mechanism that makes this trigger available in one traversal while permanently unavailable in another within the same state-accumulation model.

Thus novelty holds, but path-dependence does not.

### 4.3 divisibility_witness

`2|p` is already present in `S0+`, and closure has already generated `p = 2*k_6`. Therefore the trigger is not novel.

### 4.4 integer_witness

The same `2|p` witness path already exists at `S0+`, including `integer(k_6)`. Therefore the trigger is not novel.

### 4.5 gcd_contradiction

The trigger requires both `2|p` and `2|q` together with `gcd(p,q,1)`. `S0+` contains `2|p` and the gcd fact, but not `2|q`. The current operator set does not generate a source equality `q = 2*m` and therefore does not provide the missing path-dependent exposure needed to create `2|q`.

Thus novelty holds, but path-dependence does not.

## 5. Structural conclusion

No current rule satisfies both required properties:

`not exists R [Novelty(R) AND PathDependence(R)]`

The stronger interpretation is that the current operator set accumulates state monotonically while substitution preserves its source. Consequently, changing traversal order can change the time at which an object appears, but cannot create the required irreversible divergence in the reachable closure.

Therefore scheduling variance is not causal divergence. A difference such as `k_A != k_B` is a queue/order effect unless a transition changes the future applicability of rules.

## 6. Rejected positive-control target

`G := 2*k_6^2 = q^2` is rejected as a gate target.

It is a valid derived object, but not a path-dependent gate: the source `p = 2*k_6` remains available after peripheral substitution, so the core substitution can be applied later. The previously established analysis gives the distinction as a delay (`k_A(G)=1`, `k_B(G)=2`), not non-reachability.

This is a target rejection, not an operator failure.

## 7. Formal design outcome

`Section 0 = COMPLETE / NEGATIVE`

`exists R [Novelty(R) AND PathDependence(R)] = FALSE`

`HARNESS_REJECTED_STRUCTURAL = RECORDED`

`B1 = FORMALIZED (unused)`

`G = REJECTED AS TARGET`

`Phase 3 = NOT RUN / PERMANENTLY BLOCKED FOR THIS OPERATOR SET`

This outcome does not mean the harness construction failed operationally. It establishes a boundary of applicability: the current operator algebra does not contain the non-commutative state accumulation required for a genuine state-dependent bifurcation.

## 8. Reconsideration condition

This result must be revisited if JAMP changes the keystone property. In particular, any future operator set that consumes/invalidate sources, deactivates rules, or otherwise makes future applicability depend irreversibly on traversal history invalidates the present commutative-accumulation conclusion and requires a new Section 0 analysis.
