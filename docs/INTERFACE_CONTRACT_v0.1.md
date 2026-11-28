# JAMP-INNOVATION Interface Contract
## Cross-module boundary: JI-01 / JI-03 / JI-04 / JI-05
**Document ID:** JI-00-IC-001  
**Version:** 0.1.0-draft  
**Status:** DRAFT / NOT APPROVED FOR HARDWARE CONTROL  
**Created:** 2026-11-28  
**Scope:** Stage 1 ground demonstrator only

## 1. Purpose and authority

This document defines the minimum logical data and control boundaries required to develop and test the JAMP SUIT ground demonstrator modules independently.

It covers:
- JI-01 SUIT: sensors, sensor placement metadata, suit state and environmental observations;
- JI-03 EXOSKELETON: actuator and mechanism status, requests and interlocks;
- JI-04 AI: data ingestion, sensor fusion, bounded decision outputs and health state;
- JI-05 ENERGY: power-source, battery-management and power-distribution telemetry.

This is an interface contract, not a finished hardware specification. It does not establish safety, performance, certification, or human-use suitability. No AI output defined here may directly command a safety-critical actuator. Hardware actuation remains disabled unless a separately reviewed safety controller, physical interlocks, hazard analysis and test authorization exist.

## 2. Contract principles

1. **Explicit units:** every physical quantity carries a declared unit; no implicit unit conversion.
2. **Time provenance:** timestamps identify clock domain and synchronization quality.
3. **No silent defaults:** absent, stale, malformed or out-of-range data is invalid/unknown, never zero or healthy by default.
4. **Raw/derived separation:** preserve raw sensor records; derived/fused values identify their source record IDs and algorithm version.
5. **Fail-safe boundary:** loss of communication, invalid data, watchdog expiry or power fault transitions the relevant module to its documented safe state.
6. **Versioned evolution:** incompatible schema changes require a major version increment and a reviewed migration.
7. **Least authority:** telemetry, advisory outputs and actuator commands are distinct message classes and permissions.
8. **Reproducibility:** record firmware, software, model, calibration and configuration versions with each test run.

## 3. Logical topology

```
JI-01 sensors ───────┐
                     ├──> JI-04 data ingestion / fusion / advisory
JI-03 telemetry ─────┤                         │
                     │                         └──> advisory request only
JI-05 power telemetry┘

JI-04 advisory ──X──> direct safety-critical actuator drive

JI-03 local safety controller + hardware interlocks
    owns actuator enable, limits, emergency stop and safe-state behavior.

JI-05 power management
    owns electrical protection, current/voltage limits and power isolation.
```

The diagram is logical. Physical buses, connectors, network topology and isolation barriers are not selected by this document.

## 4. Common message envelope

Every inter-module message MUST use an envelope with these fields:

| Field | Type | Requirement |
|---|---|---|
| `schema` | string | Contract identifier, e.g. `jamp.telemetry` |
| `schema_version` | string | Semantic version, e.g. `0.1.0` |
| `message_id` | UUID | Unique message identifier |
| `source_module` | enum | `JI-01`, `JI-03`, `JI-04`, `JI-05` |
| `source_instance` | string | Stable device/instance identifier |
| `sequence` | uint64 | Monotonically increasing per source instance and stream |
| `timestamp` | RFC 3339 UTC | Source event time |
| `clock_domain` | string | Clock identifier / synchronization domain |
| `time_quality` | enum | `SYNCED`, `HOLDOVER`, `UNSYNCED`, `UNKNOWN` |
| `message_type` | enum | `TELEMETRY`, `EVENT`, `ADVISORY`, `COMMAND_REQUEST`, `ACK`, `HEARTBEAT` |
| `correlation_id` | UUID/null | Links request, response and related events |
| `payload` | object | Type-specific body |
| `integrity` | object | Transport integrity / checksum metadata where supported |

Receivers MUST reject unsupported major schema versions. Receivers MUST detect duplicate, out-of-order and replayed sequence numbers according to the stream policy. A receiver MUST NOT interpret missing fields as safe values.

## 5. Measurement record

A physical measurement payload MUST include:

| Field | Type | Requirement |
|---|---|---|
| `measurement_id` | UUID | Unique measurement |
| `sensor_id` | string | Sensor identity |
| `quantity` | string | Controlled quantity name |
| `value` | number | Numeric value; NaN/Infinity prohibited |
| `unit` | string | Explicit SI or declared derived unit |
| `status` | enum | `VALID`, `DEGRADED`, `INVALID`, `STALE`, `MISSING` |
| `uncertainty` | number/null | Value and method documented when available |
| `calibration_id` | string/null | Calibration record reference |
| `sample_period_ms` | number/null | Nominal period, not a guaranteed latency |
| `source_record_id` | string/null | Raw evidence reference for derived values |

The payload MUST additionally state valid range and freshness policy in the sensor profile. Out-of-range values MUST be marked invalid or degraded; they MUST NOT be clipped and presented as valid without retaining the original reading.

## 6. Module-specific minimum payloads

### 6.1 JI-01 SUIT telemetry

Minimum logical groups:
- body/environment sensors: temperature, humidity, pressure and motion where fitted;
- sensor placement: `sensor_id`, anatomical or equipment location code, mounting revision;
- acquisition health: sample counter, calibration state, battery/power state, self-test state;
- operator-independent equipment state: garment/module configuration ID.

Human physiological measurements are not required by this contract. If later proposed, they require a separate privacy, ethics, safety and validation review.

### 6.2 JI-03 EXOSKELETON telemetry

Minimum groups:
- joint/mechanism identity and measured position/velocity where instrumented;
- actuator temperature and electrical telemetry;
- controller state: `DISABLED`, `STANDBY`, `ENABLED`, `FAULT`, `E_STOP`;
- local limit/interlock states;
- fault code and latched-fault indicator.

The local controller MUST enforce mechanical, electrical and thermal limits independently of JI-04. Loss of upstream communication MUST NOT cause continued unbounded motion.

### 6.3 JI-04 AI outputs

AI outputs are advisory by default and MUST include:
- `model_id` and immutable model/version identifier;
- `algorithm_version`;
- input measurement IDs / sequence ranges;
- output class and numeric score where applicable;
- uncertainty or confidence semantics, explicitly defined;
- `decision_status`: `ADVISORY`, `UNKNOWN`, `INCONCLUSIVE`, `WITHDRAWN`;
- reason / rule identifiers;
- expiry time or maximum age;
- fallback state.

A confidence score is not proof. Missing, stale, contradictory or out-of-distribution inputs MUST produce `UNKNOWN` or `INCONCLUSIVE` and invoke the declared fallback. The AI module MUST NOT suppress hardware faults or override local interlocks.

### 6.4 JI-05 ENERGY telemetry

Minimum groups:
- bus and pack voltage (V);
- current (A);
- power (W), derived only from identified voltage/current samples;
- state of charge (fraction or % with estimator/version identified);
- battery/pack temperature (°C);
- protection state and fault codes;
- estimated remaining energy/runtime with method, assumptions and uncertainty;
- load-shed state and power-budget revision.

The battery management system and hardware protection remain authoritative for over-current, over/under-voltage and thermal isolation. AI estimates are advisory only.

## 7. Rates, latency and freshness

No numerical sampling rate, end-to-end latency, watchdog interval or freshness threshold is approved by version 0.1.0. These values depend on selected sensors, actuators, buses, compute hardware and hazard analysis.

Each module MUST publish a profile before integration containing:
- nominal and maximum sample rate;
- worst-case processing and transport latency;
- jitter and packet-loss assumptions;
- maximum data age;
- heartbeat period and timeout;
- clock synchronization method and error bound;
- behavior on timeout, queue overflow and reconnection.

These values are **TBD / UNKNOWN** until supported by device datasheets, bench measurements and a documented timing budget. Do not substitute illustrative values for requirements.

## 8. Control and command boundary

Version 0.1.0 defines no enabled actuator command API.

If a future command interface is proposed, it MUST be separately reviewed and include:
- authenticated source and explicit authorization;
- target actuator and bounded operating envelope;
- command ID, sequence, issue time, expiry and correlation ID;
- precondition and interlock status;
- independent local limit enforcement;
- acknowledgement and observed execution state;
- watchdog and safe-state behavior;
- emergency-stop priority that cannot be overridden by software commands.

JI-04 may provide advisory requests only. JI-03 local control and hardware safety mechanisms retain final authority. No remote or AI-originated command may bypass a physical emergency stop.

## 9. Fault and degraded-mode semantics

Common fault states:
- `OK` — self-checks passed and required inputs are fresh;
- `DEGRADED` — limited function with explicit reason and bounds;
- `FAULT` — module function unavailable or unsafe to continue;
- `UNKNOWN` — health cannot be established;
- `E_STOP` — emergency stop latched.

Required behaviors:
- invalid/stale/missing critical input: mark dependent output unknown and execute fallback;
- communications timeout: enter module-specific safe state;
- power protection event: hardware protection isolates or limits the affected path;
- AI process crash or deadline miss: withdraw advisory; local controller remains safe;
- sensor disagreement: preserve all readings, raise discrepancy event, do not silently average away conflict;
- restart: require self-test and explicit re-arm where applicable; no automatic motion on restart.

Exact safe states are module-specific and must be defined in each module's hazard analysis and card before bench operation.

## 10. Transport and encoding

Transport and physical link are intentionally undecided. Candidate options may include CAN/CAN-FD, USB, UART, Ethernet or an isolated wireless link, but selection requires a documented trade study covering bandwidth, latency, fault containment, EMI, connector safety, power and security.

The canonical logical representation is UTF-8 JSON for early bench PoCs. This is not a requirement for the final real-time transport. Binary encodings may be introduced only with schema compatibility tests and a reproducible decoder.

## 11. Security and privacy

- Authenticate module identities before accepting control-relevant messages.
- Protect integrity and freshness against spoofing, tampering and replay.
- Minimize collected data; do not place credentials, personal data or raw physiological data in public repository artifacts.
- Record security assumptions and threat model before wireless or network-connected operation.
- Fail closed when message authenticity or freshness cannot be established.

## 12. Verification requirements

Before a module claims conformance, its owner must provide evidence for:
1. schema validation and version rejection;
2. unit and range validation;
3. duplicate, replay and out-of-order handling;
4. timestamp and clock-quality handling;
5. stale-data and missing-data fallback;
6. communications loss and reconnection behavior;
7. fault propagation without suppressing the original fault;
8. local interlock independence for JI-03;
9. power protection independence for JI-05;
10. reproducible latency, jitter and throughput measurements on the selected hardware.

Each result must be recorded in the owning module's `evidence/` directory with raw logs, configuration, software/firmware versions, test method, measured values, uncertainty and reviewer disposition.

## 13. Open decisions / blockers

| ID | Decision required | Owner module(s) | Required evidence | Status |
|---|---|---|---|---|
| IC-OD-01 | Select sensors and sensor profiles | JI-01 | Datasheets, calibration and bench characterization | OPEN |
| IC-OD-02 | Select edge compute platform and runtime | JI-04 | Hardware comparison, power and latency measurements | OPEN |
| IC-OD-03 | Define AI deadlines and fallback timing | JI-04 / JI-03 | Hazard analysis and measured timing budget | OPEN |
| IC-OD-04 | Select battery chemistry, pack and BMS | JI-05 | Safety data, mass/volume and discharge tests | OPEN |
| IC-OD-05 | Select physical transport and isolation | JI-01 / JI-03 / JI-04 / JI-05 | Trade study and fault-injection results | OPEN |
| IC-OD-06 | Define exoskeleton safe states and interlocks | JI-03 | Hazard analysis, mechanical limits and bench verification | OPEN |
| IC-OD-07 | Establish numeric rate/latency/freshness budgets | All four | End-to-end timing budget and measured worst-case results | OPEN |

An OPEN decision is not permission to assume a value. Unresolved items remain blockers for the affected integration step.

## 14. Acceptance criteria for this draft

| ID | Criterion | Method | Status |
|---|---|---|---|
| AC-IC-01 | Defines common envelope and typed measurement record | Document review | NOT_REVIEWED |
| AC-IC-02 | Separates telemetry, advisory and command authority | Document review | NOT_REVIEWED |
| AC-IC-03 | Specifies stale/missing/invalid data behavior | Document review | NOT_REVIEWED |
| AC-IC-04 | Preserves local actuator and power protections | Document review | NOT_REVIEWED |
| AC-IC-05 | Leaves unmeasured rates/latencies explicitly UNKNOWN | Document review | NOT_REVIEWED |
| AC-IC-06 | Defines conformance evidence and open decisions | Document review | NOT_REVIEWED |

## 15. Change control

Changes require a reviewed pull request and a version update:
- PATCH: clarifications with no schema or behavior change;
- MINOR: backward-compatible optional fields or message types;
- MAJOR: breaking schema, semantics, safety boundary or authority changes.

Each implementation MUST pin the exact contract version and commit. A module must not claim conformance to a moving draft.

## 16. Explicit exclusions

This contract does not specify or authorize:
- fall-arrest or high-altitude fall protection;
- underwater or space operation;
- closed-loop life support;
- human-subject testing;
- medical or physiological decision-making;
- autonomous actuator control by AI;
- production deployment or integration into the main JAMP product.

These remain outside Stage 1 scope under D-25 through D-27.
