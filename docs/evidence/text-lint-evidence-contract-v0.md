# Text-Lint Evidence Contract v0

## Status
Design contract for deterministic text-lint observations. This contract does not classify text as AI-generated or human-written.

## Epistemic rule
A detected pattern is an observation, not a verdict.

OBSERVED -> VERIFIED -> INFERRED -> UNKNOWN

No detector result may assert authorship, intent, quality, or probability of AI generation unless a separate validated experiment explicitly defines and supports that claim.

## Observation envelope
Each detected text pattern is represented as an EXP-22 AtomicObservation.

Required content:
- pattern_id: P01-P41
- span_start
- span_end
- matched_text
- evidence_type

Optional contextual fields MUST NOT encode verdicts.

## Forbidden semantics
The detector MUST NOT emit:
- verdict
- confidence
- supported
- rejected
- ai_generated
- human_written

## Provenance
Every observation MUST be reproducible from source_ref + detector identity/version + observed content + structural span. Detection MUST NOT mutate source text.

## Pattern catalogue
| ID | Pattern | Evidence class |
|---|---|---|
| P01 | Significance inflation | lexical/contextual |
| P02 | Notability name-dropping | attribution/contextual |
| P03 | Superficial -ing tails | syntactic |
| P04 | Promotional language | lexical |
| P05 | Vague attribution | attribution |
| P06 | Rule-of-three cadence | structural |
| P07 | AI vocabulary | lexical heuristic |
| P08 | Copula avoidance | syntactic |
| P09 | Negative parallelism | syntactic |
| P10 | Rule of three | structural |
| P11 | Synonym cycling | lexical/semantic |
| P12 | False ranges | structural/semantic |
| P13 | Passive/subjectless fragments | syntactic |
| P14 | False agency | semantic |
| P15 | Lazy extremes | lexical |
| P16 | Em/en dash | punctuation |
| P17 | Boldface overuse | markup |
| P18 | Inline-header lists | structure |
| P19 | Title Case headings | structure |
| P20 | Emojis | markup |
| P21 | Curly quotes | Unicode/style |
| P22 | Excessive structure | document structure |
| P23 | Fragmented headers | structure |
| P24 | Diff-anchored writing | lexical/structural |
| P25 | Chatbot artifacts | lexical |
| P26 | Cutoff/speculative disclaimer | modality |
| P27 | Sycophantic tone | discourse |
| P28 | Reasoning-chain artifacts | discourse |
| P29 | Acknowledgment loops | discourse |
| P30 | Signposting | discourse |
| P31 | Filler phrases | lexical |
| P32 | Excessive hedging | modality |
| P33 | Adverb pile | lexical/statistical |
| P34 | Generic positive conclusion | discourse |
| P35 | Hyphenated word-pair overuse | lexical/statistical |
| P36 | Vague declarative | semantic/lexical |
| P37 | Persuasive authority tropes | discourse |
| P38 | Staccato drama | sentence structure |
| P39 | Aphorism formula | syntax/discourse |
| P40 | Conversational opener | discourse |
| P41 | Narrator-distance / WH opener | syntax/discourse |

The catalogue is a detector inventory, not a claim that every pattern is uniquely caused by AI.

## Decision boundary
Detection produces evidence. A separate policy or human review step may decide whether to preserve, rewrite, or remove text. That decision MUST be represented separately from the observation.

## Fail-closed
- Missing source text: UNKNOWN/HOLD.
- Invalid span: reject observation.
- Unknown pattern ID: reject observation.
- Non-canonical JSON: reject observation.
- Forbidden semantic key: reject observation.
- Missing detector version: reject observation.
- Detection failure: do not synthesize PASS.