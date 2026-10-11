# Shadow ADR — Causal Blind Spot

Status: SHADOW / NON-NORMATIVE / READ-ONLY
Origin: EXP-27
Scope: research analysis only. This document does not modify Frozen Core, PROVENANCE-CONTRACT-v0, or runtime behavior.

## Decision context

EXP-27 identified a distinction between content determinism and causal/lineage determinism.

The audited execution identity is derived from intrinsic execution content:

plan_hash + question_hash + parameters + observations + trace_hash + state_hash

The Frozen Provenance Contract v0 requires execution_id and provenance references, but does not prescribe a deterministic cryptographic construction that binds execution identity to parent_ref or an equivalent causal-graph identifier.

Therefore:

Content identity answers:
"Is this execution content reproducibly the same?"

Lineage identity answers:
"Did this execution occur in this exact causal context?"

The current contract normatively addresses the first question. The second is not established as a contract invariant.

## Criticality task — Context Switch / Grafting

Research scenario to model:

1. Branch A produces a legitimately generated Raw Evidence object.
2. The Raw Evidence content is copied into branch B.
3. Branch B presents that evidence inside a different causal graph.
4. No intrinsic content field changes.
5. The system accepts the evidence because content hashes remain valid.

Potential harm is not assumed. It must be demonstrated.

The required research question is:

Does any supported JAMP use case rely on the causal context itself as a security, correctness, authorization, attribution, or scientific-validity boundary?

If no material use case requires that property, lineage-blindness may be an acceptable simplification rather than a vulnerability.

If a material use case does require it, the gap becomes a candidate security/correctness requirement for a future contract.

This document records the scenario as a threat model, not as an observed exploit.

## Trade-off task — Lineage binding versus reuse

Candidate rule:

execution_hash = H(intrinsic_execution_payload + parent_ref)

Immediate consequence:

Two executions with identical intrinsic content but different parents would obtain different identities.

Benefit:
- causal context becomes cryptographically bound to execution identity;
- grafting across parents can invalidate the identity.

Cost:
- identical computations in different causal contexts cease to share the same execution identity;
- memoization/cache reuse may decrease;
- storage and recomputation pressure may increase;
- legitimate cross-branch reuse semantics become harder to express.

This exposes a genuine design choice:

### Option A — Content identity only

Keep the existing execution identity semantics.

Pros:
- maximal content-level reuse;
- simple deterministic memoization;
- preserves current contract boundary.

Cons:
- lineage remains separately represented;
- cryptographic identity does not itself reject a causal graft.

### Option B — Lineage-bound execution identity

Include parent/lineage context in the execution identity.

Pros:
- identity directly commits to causal context;
- stronger protection against cross-context grafting.

Cons:
- reduces identity reuse across causal contexts;
- may conflict with legitimate memoization semantics;
- would require a new normative contract decision.

### Option C — Dual identity

Keep a reusable content identity and add a separate causal-context identity/binding.

Example conceptual model:

content_id = H(intrinsic_execution_payload)
lineage_id = H(content_id + canonical_lineage_context)

This preserves content-level memoization while allowing applications that require causal binding to verify lineage explicitly.

This option is listed for research comparison only; it is not selected by this Shadow ADR.

## Current architectural position

No option is selected.

The current position is:

- WAIT / READ-ONLY;
- Frozen Core remains LOCKED;
- PROVENANCE-CONTRACT-v0 remains FROZEN;
- no make_execution() patch;
- no normative requirement is added;
- no exploit is claimed.

The next research step is empirical/analytical: identify whether a real supported JAMP use case can be harmed by context grafting, then quantify the cost of candidate lineage-binding models.

## Evidence boundary

The architectural gap is supported by the EXP-27 audit of the Frozen Provenance Contract v0 and the make_execution() implementation.

The audit does not establish:
- that a graft has occurred;
- that an attacker can exploit one in production;
- that lineage binding is required;
- or that any candidate design is preferable.

Those remain research questions.
