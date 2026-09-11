# Rigorous Experimental Protocol v1

Status: CLOSED
Applies to: state-dependent harness (not Track A)
Anchor: 49a5c86

## 1. Interface invariants

1. Strategy may select candidates and thereby determine traversal.
2. Exposure is a function of current state only.
3. Exposure receives no strategy identifier.
4. Exposure receives no selection history.
5. Candidate selection does not directly modify exposure.
6. Strategy can affect exposure only through the visited state.
7. Closure operates on the current state and does not inspect strategy identity.
8. Compared strategies use the same state representation, operator set, closure semantics, and result predicates.

## 2. Design completeness

A design is complete only if all of the following are fixed before implementation:

- parameter types and values;
- state representation;
- expression representation and canonicalization;
- rule representation;
- candidate representation;
- strategy interfaces;
- candidate generation;
- exposure signature and trigger predicates;
- closure invocation pattern;
- positive-control traversals;
- pre-registered prediction;
- primary and secondary endpoints;
- kill criteria;
- interpretation rules.

Any unresolved implementation choice is a design incompleteness and blocks freeze.

## 3. Negative control

The negative control is executed before the positive control.

PASS requires that exposure is state-dependent and strategy-blind under the declared interface invariants.

FAIL produces terminal outcome `HARNESS_INVALID` and prohibits content interpretation.

## 4. Positive control

The positive control is executed after the negative control passes.

The positive control must contain two prescribed traversals over the same initial state.

PASS requires a mechanically checkable structural bifurcation: a state-dependent trigger is reachable on one prescribed traversal and unreachable on the other under the fixed traversal budget.

A difference caused only by traversal delay is not a positive-control pass.

FAIL produces terminal outcome `HARNESS_REJECTED` and prohibits modification of the mechanism in response to the failed control.

## 5. Pre-registered prediction

The prediction is frozen before content runs.

The prediction must specify:

- compared strategies;
- initial states or roots;
- the traversal mechanism;
- the state-dependent trigger;
- the exposed rule;
- the predicted direction of the effect;
- the conditions under which the prediction is evaluated.

A prediction is not changed after observing content results.

## 6. Endpoints

Primary endpoint:

`closure_RANDOM != closure_TARGETED`

Secondary endpoint:

`|closure_RANDOM| != |closure_TARGETED|`

Exploratory endpoints may describe trajectory, first-trigger step, or time-to-closure only when pre-registered.

## 7. Kill criteria

Define:

`K1 := closure_RANDOM != closure_TARGETED`

`K2 := |closure_RANDOM| != |closure_TARGETED|`

`KILL := not K1 and not K2`

If the controls pass and both K1 and K2 are false across all declared comparison cases, the result is a null-channel result. It is not evidence of a successful causal channel.

## 8. Construction principle

No mechanism is accepted because it produces a desired result.

A positive-control mechanism is valid only when:

1. the neutral control does not itself produce the claimed causal separation; and
2. an independently prescribed input is known before content execution to traverse the hypothesized causal channel.

Observed traces cannot be used retroactively to define the positive control.

## 9. Terminal outcome matrix

| Condition | Terminal outcome |
|---|---|
| Negative control fails | `HARNESS_INVALID` |
| Negative control passes; positive control fails | `HARNESS_REJECTED` |
| Both controls pass; prediction differs from observation | `PREDICTION_REJECTED` |
| Both controls pass; KILL is true | `HARNESS_NULL` |
| Both controls pass; K1 is true | `CAUSAL_DIVERGENCE` |
| Both controls pass; K1 false and K2 true | `SIZE_DIVERGENCE` |

## 10. Pre-registration boundary

The design becomes frozen at the recorded pre-registration boundary.

After freeze, any change to parameters, mechanism, exposure, strategy interface, closure invocation, positive control, prediction, endpoints, kill criteria, or interpretation rules creates a new design version and invalidates numerical results obtained under the changed design as results of the previous version.

## 11. Rules for exit

A design may enter implementation only if:

- negative-control specification is complete;
- positive-control specification is complete;
- prediction is complete;
- endpoints and kill criteria are complete;
- no implementation choice remains unspecified.

A design remains blocked when any one of these conditions is false.