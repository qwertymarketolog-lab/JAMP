# AI Automation Abuse Case Study: Streaming Royalty Fraud

## Status

**Design / risk-learning note only.** This document applies JAMP's existing evidence-first and agent trust-boundary principles to one documented case. It does not add runtime enforcement or claim that any new control is implemented.

## Verified case summary

On October 6, 2026, the U.S. Department of Justice announced that Michael Smith of North Carolina had been sentenced to 18 months in prison after pleading guilty to conspiracy to commit wire fraud. The DOJ says that, between 2017 and 2024, he created thousands of fraudulent streaming accounts, used software to stream songs he controlled, and collected more than $8 million in royalties from Spotify, Apple Music, Amazon Music, and YouTube Music. Hundreds of thousands of songs were AI-generated; the scheme used bots to make automated plays appear to be genuine consumer activity.

Primary sources:

- [U.S. Department of Justice — sentencing announcement, October 6, 2026](https://www.justice.gov/usao-sdny/pr/north-carolina-man-sentenced-18-months-prison-super-intelligence-assisted-music)
- [U.S. Department of Justice — guilty plea announcement, March 19, 2026](https://www.justice.gov/usao-sdny/pr/north-carolina-man-pleads-guilty-music-streaming-fraud-aided-artificial-intelligence-0)

The relevant distinction is not whether AI generated the songs. The prosecuted conduct involved deceptive artificial engagement, fraudulent accounts and payment details, and obtaining royalties through that deception. This case is an example, not a general legal conclusion about every use of AI-generated content or automation.

## JAMP-relevant risk pattern

The case illustrates a failure pattern that can arise in any system where automated activity affects money, ranking, reputation, access, or allocation of shared resources:

1. **Synthetic activity is represented as genuine activity.** Bot-generated plays were presented as consumer listening.
2. **Identity and account signals are falsified.** Fraudulent accounts and payment details supported the apparent legitimacy of activity.
3. **Automation scales the deception.** A large volume of generated content and automated plays increased the scale of the scheme.
4. **The system's output affects a consequential allocation.** Royalty payments were diverted from legitimate rights holders.
5. **Evasion is deliberate.** Activity was distributed to reduce the chance of detection.

These are risk indicators, not a claim that high volume, AI-generated content, or automation alone proves fraud.

## Design implications for JAMP

Treat these as review requirements for future integrations and agent capabilities, **not as verified existing runtime controls**.

- **Proposal is not authorization.** An AI model may propose an action or interpret observations; it must not grant itself permission to perform consequential actions.
- **Preserve the identity of activity.** Do not label automated events as human activity, or simulated/test events as real user engagement.
- **No deceptive engagement or payout manipulation.** Do not build or operate agents intended to fabricate views, listens, clicks, ratings, conversions, users, or other signals used to allocate money or benefits.
- **No evasion of integrity controls.** Do not help conceal automation, rotate identities to defeat anti-fraud systems, or bypass platform limits and policies.
- **Require authorization for side effects.** Publishing, account creation, financial actions, and other external mutations require a documented, policy-compliant authorization boundary; access to an API is not by itself authorization.
- **Keep evidence traceable.** Preserve source, timestamp, actor/agent identity where available, action type, target, result, and relevant raw response or artifact. Keep raw observations separate from derived conclusions.
- **Fail closed under uncertainty.** Missing, conflicting, stale, or inconclusive evidence must not be promoted to VERIFIED or used to justify an unapproved consequential action. Use HOLD/REFUSE according to the applicable contract.
- **Do not confuse anomaly with proof.** Unusual volume may justify review but is not, by itself, proof of malicious intent. Record the evidence and uncertainty.

## Suggested review questions for future integrations

Before enabling an agent that interacts with a third-party platform, reviewers should ask:

1. What real-world resource, payment, ranking, or entitlement can this action affect?
2. Could the action make synthetic or automated activity appear to be genuine user activity?
3. Are account identity, consent, ownership, and authorization established by evidence rather than model assertions?
4. Does the workflow bypass or attempt to evade platform integrity controls?
5. Are external side effects bounded, attributable, auditable, and reversible where feasible?
6. What happens when evidence or authorization is missing? The expected outcome is HOLD/REFUSE, not a guessed PASS.
7. Can a reviewer reconstruct the action from a terminal, source-linked evidence trail?

## Scope and non-goals

- Documentation only; no runtime, API, router, Product Matrix, workflow, test, or dependency changes.
- No new fraud-detection capability is claimed.
- No change to model qualification or routing eligibility.
- No claim that this case establishes the legality of unrelated AI-generated content or ordinary automation.
- Frozen Core `src/jamp/run.py` remains out of scope; required invariant: blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`, `Δ = 0`.

## Review disposition

This note is a design reference for future integration reviews. It is not evidence that a control has been implemented or that any runtime is compliant. Any future enforcement change requires a separate scoped implementation, tests, and terminal Run → Job → artifact evidence.
