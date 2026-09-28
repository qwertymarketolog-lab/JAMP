# AnyModel LIVE_AVAILABLE 77×30 Contract v0

## State

- State: **DESIGN / OPEN**
- Contract: `ANYMODEL-LIVE-AVAILABLE-77X30-V0`
- Scope: **77 models × 30 checks = 2,310 checks**
- N4 snapshot: `439283f87427380a35e210d41f8045e0c240307138dc787442858663f100f6ef`
- N4 artifact: GitHub Actions artifact **10962081420**
- N4 snapshot schema: `anymodel-n4-live-catalog-v1`
- N4 source endpoint: `https://anymodel.org/v1/models`
- N4 observed at: `2026-09-28T09:37:43.158379+00:00`
- N4 HTTP status: **200**
- N4 snapshot count: **78**
- Explicit exclusion: `am/kimi-k3`
- Derived LIVE_AVAILABLE count: **77**
- Frozen Core: `src/jamp/run.py`
- Frozen Core blob: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`
- Required Core delta: **Δ = 0**

## Set identity

The contract set is the exact N4 snapshot set minus exactly `am/kimi-k3`.

The N4 snapshot itself has digest `331c26f5aa531db028063dd3fa267acca98d3e81a0140529eecaad6714218039`.
The derived 77-ID set has digest **`439283f87427380a35e210d41f8045e0c240307138dc787442858663f100f6ef`**.

### Canonical 77 IDs

1. `ag/claude-sonnet-4-6`
2. `ag/gemini-2.5-flash`
3. `ag/gemini-2.5-flash-lite`
4. `ag/gemini-3-flash`
5. `ag/gemini-3.1-flash-image`
6. `ag/gemini-3.1-flash-lite-preview`
7. `ag/gemini-3.1-pro-low`
8. `ag/gemini-3.6-flash-high`
9. `ag/gemini-3.6-flash-low`
10. `ag/gemini-3.6-flash-medium`
11. `ag/gemini-3.7-flash-high`
12. `ag/gemini-3.7-flash-low`
13. `ag/gemini-3.7-flash-medium`
14. `ag/gemini-pro-agent`
15. `ag/gpt-oss-120b-medium`
16. `am/diffusiongemma-26b-a4b-it`
17. `am/flux.1-dev`
18. `am/flux.2-klein-4b`
19. `am/free`
20. `am/gpt-oss-20b`
21. `am/laguna-xs-2.1`
22. `am/llama-3.2-11b-vision-instruct`
23. `am/nemotron-3-nano-omni-30b-a3b-reasoning`
24. `am/nemotron-3-super-120b-a12b`
25. `am/nemotron-3-ultra-550b-a55b`
26. `am/nemotron-3.5-content-safety`
27. `am/nemotron-3.5-lightning-30b-a3b`
28. `am/riva-translate-4b-instruct-v2`
29. `cc/claude-haiku-4-5-20251001`
30. `cc/claude-opus-4-6`
31. `cc/claude-opus-4-7`
32. `cc/claude-opus-4-8`
33. `cc/claude-opus-5`
34. `cc/claude-sonnet-4-6`
35. `cc/claude-sonnet-5`
36. `cx/gpt-5.5`
37. `cx/gpt-5.5-review`
38. `cx/gpt-5.6-luna`
39. `cx/gpt-5.6-luna-review`
40. `cx/gpt-5.6-sol`
41. `cx/gpt-5.6-sol-review`
42. `cx/gpt-5.6-terra`
43. `cx/gpt-5.6-terra-review`
44. `cx/gpt-6-astra`
45. `cx/gpt-6-luna`
46. `cx/gpt-6-luna-review`
47. `cx/gpt-6-sol`
48. `cx/gpt-6-sol-review`
49. `cx/gpt-image-1.5`
50. `cx/gpt-image-2`
51. `ds/deepseek-v4-flash`
52. `ds/deepseek-v4-pro`
53. `flow/nano-banana`
54. `flow/nano-banana-lite`
55. `flow/nano-banana-pro`
56. `gcli/grok-4.5`
57. `gcli/grok-4.6`
58. `gcli/grok-4.7`
59. `gcli/grok-4.7-build-fast`
60. `glm/glm-4.6v`
61. `glm/glm-4.7`
62. `glm/glm-5`
63. `glm/glm-5.1`
64. `glm/glm-5.2`
65. `glm/glm-5.3`
66. `glm/glm-5.3-flash`
67. `kmc/k3`
68. `kmc/kimi-for-coding`
69. `nano-banana`
70. `nano-banana-lite`
71. `nano-banana-pro`
72. `qwen/qwen3.7-max`
73. `qwen/qwen3.7-plus`
74. `qwen/qwen3.8-max`
75. `xai/grok-imagine-image`
76. `xai/grok-imagine-image-2.0`
77. `xai/grok-imagine-image-quality`

## 30-check contract

Each of the 77 canonical IDs receives exactly 30 checks.

Required matrix cardinality:

- models = 77
- checks/model = 30
- total checks = **2,310**
- unique model IDs = 77
- `am/kimi-k3` must be absent

The audit MUST consume this frozen ID set. A live catalog response MUST NOT silently add, remove, rename, or reorder the contract population.

## Provenance

Every execution artifact MUST record at minimum:

- contract ID and version;
- exact contract-set digest: `439283f87427380a35e210d41f8045e0c240307138dc787442858663f100f6ef`;
- N4 artifact ID: `10962081420`;
- N4 snapshot digest: `331c26f5aa531db028063dd3fa267acca98d3e81a0140529eecaad6714218039`;
- experiment/audit commit SHA;
- runtime timestamp UTC;
- endpoint;
- model ID;
- check ID;
- raw observation/evidence reference.

## Fail-closed validation

Execution MUST terminate non-zero before model checks if any invariant fails:

1. contract set contains exactly 77 IDs;
2. IDs are unique;
3. exact set equals the canonical list above;
4. `am/kimi-k3` is absent;
5. checks/model is exactly 30;
6. expected total is exactly 2,310;
7. contract-set digest matches `439283f8…f6ef`;
8. Frozen Core blob remains `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`;
9. N4 provenance fields are present and match the frozen snapshot;
10. missing/partial model evidence is **INCONCLUSIVE/FAILED**, never PASS.

A current live catalog count alone is insufficient evidence for contract identity.

## Evidence classification

- **OBSERVED:** N4 HTTP response and snapshot artifact.
- **VERIFIED:** exact 78→77 set derivation, cardinality, uniqueness and digest.
- **INFERRED:** none required for population identity.
- **UNKNOWN:** runtime behavior of the 77×30 audit until its terminal artifact exists.

## State transition

`DESIGN / OPEN` → execution → `VERIFIED`, `INCONCLUSIVE`, or `FAILED`.

No terminal runtime state is asserted by this contract commit alone.
