# State-Dependent Harness — Five-Layer Framework

Status: FRAMEWORK

## Layer 1 — Parameters

`Parameter := Primitive`

`ROOTS : Set[Primitive]`
`N : Integer`
`MAX_OBJECTS : Integer`
`SEED : Integer`
`BUDGET : Integer`

## Layer 2 — Mechanism

`State := finite canonicalized collection of Expr`

`Expr := canonical expression value`

`Rule := (name, trigger_predicate, effect_function)`

`Candidate := (new_state_or_expr, operator, parents)`

`Strategy := State -> Candidate`

`candidate_set : State -> Set[Candidate]`

`exposure : State -> frozenset[Rule]`

`trigger_R : State -> Bool`

`closure : State -> State`

`exposure(S) := { R | trigger_R(S) = true }`

`closure(S) := least fixed point of the declared closure rules over S`

## Layer 3 — Positive control

`T_A : State_0 -> State_1 -> ... -> State_k`

`T_B : State_0 -> State'_1 -> ... -> State'_j`

`T_A(0) = T_B(0)`

`StructuralBifurcation(G,T_A,T_B) :=
    exists k,j : G in T_A(k) and for all i <= j, G not in T_B(i)`

`T_A != T_B`

`G := canonical expression or state predicate trigger`

## Layer 4 — Prediction

`Prediction := (strategy_A, strategy_B, roots, trigger, rule, direction, conditions)`

`P : FrozenDesign -> PredictedOutcome`

`P` is fixed before content execution.

## Layer 5 — Endpoints / Kill

`closure_RANDOM : Result`

`closure_TARGETED : Result`

`K1 := closure_RANDOM != closure_TARGETED`

`K2 := |closure_RANDOM| != |closure_TARGETED|`

`KILL := not K1 and not K2`

`PRIMARY := K1`

`SECONDARY := K2`

`EXPLORATORY := pre-registered trajectory or timing predicates`
