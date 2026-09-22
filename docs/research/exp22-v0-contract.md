# EXP-22 v0 Contract: Atomic Observation Integrity

## Status

**Design specification locked.** This document defines the v0 contract for `jamp.atomic_observation`. It does not authorize production implementation and does not constitute GREEN evidence.

## 1. Canonical API

The implementation MUST expose:

```python
@dataclass(frozen=True)
class AtomicObservation:
    id: str
    source_ref: str
    atom_type: str
    operator_id: str
    operator_version: str
    content: Any
    params: Dict[str, Any]

def create_atomic_observation(
    *,
    content: Any,
    atom_type: str,
    source_ref: str,
    operator_id: str,
    operator_version: str,
    params: Dict[str, Any]
) -> AtomicObservation:
    ...
```

The returned object MUST expose `.id`.

## 2. Identity Preimage

The identity digest is computed from a deterministic structural preimage containing exactly these seven components:

1. `source_ref`
2. `atom_type`
3. `operator_id`
4. `operator_version`
5. canonicalized `content`
6. canonicalized closed structural identity parameters
7. the fixed identity schema/version marker for this contract

Only the following parameter keys may contribute to identity:

```python
ALLOWED_ID_PARAMS = {"segment_index", "span_start", "span_end"}

def _extract_closed_identity_params(params: dict) -> dict:
    return {
        k: params[k]
        for k in sorted(ALLOWED_ID_PARAMS)
        if k in params and params[k] is not None
    }
```

Keys outside `ALLOWED_ID_PARAMS` are excluded from identity computation. Missing or `None` values are omitted.

The serialized preimage MUST use an unambiguous, deterministic field encoding. Implementations MUST NOT depend on Python object representation, dictionary insertion order, memory addresses, timestamps, or other runtime noise.

### v0 Canonical Preimage Serialization (Locked)

For v0, the exact canonical identity preimage is the UTF-8 string formed by joining seven components with the literal delimiter `||`:

```text
v0||source_ref||atom_type||operator_id||operator_version||C(content)||C(filtered_params)
```

Component order and serialization are fixed as follows:

| Index | Component | Canonical serialization | Null / missing handling |
|---:|---|---|---|
| 0 | Schema version | Literal string `v0` | Required |
| 1 | `source_ref` | String value encoded as UTF-8 | Required; MUST be a non-empty string |
| 2 | `atom_type` | String value encoded as UTF-8 | Required |
| 3 | `operator_id` | String value encoded as UTF-8 | Required |
| 4 | `operator_version` | String value encoded as UTF-8 | Required |
| 5 | `content` | `C(content)` using canonical JSON below | Required |
| 6 | filtered identity parameters | `C(filtered_params)` using canonical JSON below | Missing/empty allowlist serializes as `{}` |

The canonical JSON function is exactly:

```python
json.dumps(
    value,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=True,
    allow_nan=False,
)
```

The filtered parameter object is exactly:

```python
ALLOWED_ID_PARAMS = {"segment_index", "span_start", "span_end"}

filtered_params = {
    k: params[k]
    for k in sorted(params.keys())
    if k in ALLOWED_ID_PARAMS and params[k] is not None
}
```

The preimage construction is therefore normatively defined as:

```python
CANONICAL_DELIMITER = "||"

def compute_canonical_preimage(
    source_ref: str,
    atom_type: str,
    operator_id: str,
    operator_version: str,
    content: Any,
    params: dict,
) -> str:
    allowed_keys = {"segment_index", "span_start", "span_end"}
    filtered_params = {
        k: params[k]
        for k in sorted(params.keys())
        if k in allowed_keys and params[k] is not None
    }

    c_content = json.dumps(
        content,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    c_params = json.dumps(
        filtered_params,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )

    parts = [
        "v0",
        source_ref,
        atom_type,
        operator_id,
        operator_version,
        c_content,
        c_params,
    ]
    return CANONICAL_DELIMITER.join(parts)
```

The identity digest is exactly:

```python
observation_id = hashlib.sha256(
    compute_canonical_preimage(
        source_ref,
        atom_type,
        operator_id,
        operator_version,
        content,
        params,
    ).encode("utf-8")
).hexdigest()
```

No alternative delimiter, field order, coercion, escaping scheme, serialization format, or implicit normalization is permitted for v0. This serialization definition is normative and closes the v0 preimage-format ambiguity.

## 3. Canonicalization

Canonical JSON serialization MUST use:

```python
json.dumps(
    value,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=True,
    allow_nan=False,
)
```

Canonicalization is applied independently to the content and closed identity-parameter subsets.

There is **no implicit numeric/string coercion**. Unsupported or non-canonicalizable JSON values MUST fail closed with `ValueError`.

## 4. Semantic Neutrality

The following evaluation keys are a closed forbidden set:

```python
FORBIDDEN_SEMANTIC_KEYS = {
    "verdict",
    "supported",
    "rejected",
    "confidence",
}
```

Forbidden keys MUST be rejected when encountered in the incoming content/payload structure according to the implementation's recursive validation rule.

`status` is permitted only as operational lifecycle metadata (for example, `raw` or `segmented`). It MUST NOT be interpreted or populated as an evaluation verdict.

## 5. Integrity Invariants

The implementation and research tests MUST establish:

- Determinism.
- Payload sensitivity.
- Source/provenance binding.
- Transcript-boundary sensitivity.
- Identity separation / composite isolation.
- Semantic neutrality.

These invariants describe identity and schema integrity only. They do not establish semantic truth, causal validity, or research conclusions.

## 6. Governance Boundary

PR #144 remains the RED/specification anchor and MUST NOT contain the production implementation.

A future implementation PR (PR #145 or successor) is a separate deliberate production change. It requires explicit authorization to modify the Frozen Core and must independently produce implementation/test evidence before any GREEN claim.

**Frozen Core state for PR #144:** `Δ src/jamp = 0`.

**This document is a design contract, not runtime evidence.**
