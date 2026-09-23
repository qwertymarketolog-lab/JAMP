# JAMP Technology Direction

## Status

This document defines the product and technology direction for JAMP beyond the current experimental core.

JAMP is not intended to compete with foundation models. Its role is to provide an **evidence-first layer between AI observations and consequential decisions**.

The central principle is:

> AI searches and observes. JAMP verifies, decomposes, connects, compares, preserves provenance, exposes conflicts, and records the evidence history.

JAMP therefore treats an AI model as a perception sensor rather than an authority.

## 1. Technology position

A practical AI technology stack can be viewed as:

1. **Infrastructure** — compute, storage, networking, browsers, operating systems and databases.
2. **Models** — LLMs, vision models, speech models, retrieval models and other AI systems.
3. **JAMP evidence layer** — observations, evidence, provenance, conflict detection, deterministic arbitration, experiments and replay.
4. **Applications** — research, engineering, enterprise knowledge, browser research, compliance, analytics and decision-support products.

JAMP occupies layer 3.

The objective is not to make the model appear more confident. The objective is to make the surrounding system able to distinguish:

- observed from inferred;
- source from interpretation;
- supported from unsupported;
- agreement from independent confirmation;
- correlation from demonstrated causality;
- known from unknown;
- current evidence from historical evidence.

## 2. Core technology direction

The long-term JAMP platform is an **Evidence-First Research Infrastructure / Research OS**.

The technology roadmap is:

**Frozen Core → Evidence → Provenance → Conflict → Atomic Observation → Multi-AI Federation → Experiment Engine → Replay → Adaptive Research Loop → Research OS / Domain Products**

The existing Frozen Core remains protected.

Product layers must not require modifications to `src/jamp/run.py` merely to support a new application, integration, UI, performance optimization or commercial product.

The preferred integration model is:

**Application / Extension / Browser / API → JAMP adapter → JAMP evidence infrastructure → Frozen Core**

## 3. Where JAMP can be applied

### 3.1 Evidence-First Browser

The first concrete product direction is a browser extension that adds a JAMP evidence layer to existing browsers.

Initial target:

- Chromium-compatible browsers;
- Chrome;
- Edge;
- Brave;
- Opera;
- Vivaldi;
- Yandex Browser, subject to compatibility verification.

The extension does not need to replace the browser engine.

It can provide:

- Verify this page;
- Verify selected text;
- Compare sources;
- Extract claims;
- Identify supporting and conflicting evidence;
- Track source timestamps;
- Build an evidence graph;
- Preserve research provenance;
- Replay a research session.

A later standalone JAMP Browser can use Chromium/CEF or another suitable browser engine while keeping the evidence layer separate from the rendering engine.

### 3.2 Research and knowledge work

JAMP can support researchers who need an auditable answer rather than a conversational answer.

Examples:

- literature and source comparison;
- technical research;
- market research;
- competitive research;
- fact checking;
- investigation of conflicting sources;
- long-running research projects;
- reproducible research notebooks.

The important product unit is not a chat response. It is an **evidence-backed research result with provenance**.

### 3.3 Software engineering

JAMP can operate around AI coding systems as an evidence and verification layer.

Potential uses:

- verify claims made by coding agents;
- preserve repository evidence;
- compare implementation against requirements;
- track CI and test evidence;
- correlate changes with experimental results;
- preserve commit / workflow / artifact lineage;
- distinguish a passing check from a demonstrated causal conclusion;
- replay an engineering investigation.

This direction is especially compatible with the existing JAMP experimental methodology.

### 3.4 Science and experimental systems

JAMP can provide infrastructure for controlled experiments where the system must preserve:

- exact workload identity;
- target commit;
- experimental boundary;
- measurements;
- hypotheses;
- interventions;
- controls;
- artifacts;
- statistical tests;
- conflicts;
- inconclusive results;
- replay information.

The system must not manufacture a PASS when the evidence is insufficient.

### 3.5 Enterprise knowledge and due diligence

JAMP can be applied where organizations combine information from many sources and need an audit trail.

Potential domains:

- technical due diligence;
- vendor research;
- procurement research;
- compliance evidence;
- internal knowledge verification;
- incident investigation;
- risk research;
- policy and procedure verification;
- financial or operational research.

The product should preserve the distinction between source material and conclusions derived from it.

### 3.6 Multi-AI systems

JAMP can act as an arbitration and evidence layer between multiple AI systems.

Different models can independently produce observations.

JAMP can then:

1. record each observation;
2. bind it to its source and context;
3. compare observations;
4. detect agreement and conflict;
5. request additional evidence;
6. preserve unresolved disagreement;
7. produce a deterministic evidence state.

This avoids treating model majority vote as automatic truth.

### 3.7 Physical systems / JAMP Edge

JAMP can also operate around physical devices and embedded systems as an **evidence layer for real-world observations**.

The target is not to replace the device firmware or safety-critical controller. The preferred architecture is:

```
Device sensors / logs / events
            │
            ▼
      Edge Adapter
            │
            ▼
     JAMP Evidence Layer
            │
      ┌─────┴─────┐
      │           │
   AI sensors   Evidence UI
      │           │
      └─────┬─────┘
            ▼
   Provenance / Conflict /
   Experiment / Replay
```

Possible device classes include:

- smart TVs and media devices;
- washing machines and household appliances;
- refrigerators and HVAC systems;
- robot vacuums and domestic robots;
- vehicles and mobility systems;
- industrial equipment and PLC-connected systems;
- IoT devices and sensor networks;
- embedded Linux and Android devices.

The integration depends on the device platform.

### Embedded MCU / RTOS

Small controllers may have limited RAM, flash and CPU resources and therefore may not be suitable for the complete JAMP runtime. In that case, a lightweight device adapter can expose telemetry, events and diagnostics to a gateway running JAMP-compatible evidence infrastructure.

Typical implementation environments may include:

- STM32-class microcontrollers with vendor HAL/SDK and an RTOS;
- ESP32-class devices with an embedded SDK/RTOS;
- Zephyr or similar embedded operating systems;
- proprietary appliance firmware.

### Embedded Linux / Android

Devices with Linux or Android-class operating systems may support a local JAMP adapter or service when the vendor platform permits third-party software.

Examples include:

- embedded Linux services;
- Android applications or services;
- gateway daemons;
- local diagnostic collectors.

The exact integration boundary must be verified per device and vendor; JAMP should not assume root access, firmware modification or unrestricted system APIs.

### Gateway architecture

For constrained devices, the preferred deployment is:

```
Device
  │
  ├── sensors
  ├── events
  └── diagnostics
        │
        ▼
  JAMP Edge Adapter
        │
        ▼
  Evidence / Provenance
        │
        ├── AI perception
        ├── conflict detection
        ├── experiments
        └── replay
```

A gateway may be a phone, home server, router-class computer, Raspberry Pi-class device, industrial edge computer or cloud-connected service, depending on latency, privacy and connectivity requirements.

### Safety boundary

JAMP Edge is primarily **observational and evidentiary**.

It must not silently become a safety-critical control system. For appliances, vehicles, industrial machinery and other systems where incorrect commands can create physical risk, control functions remain under the device's certified or independently engineered control layer.

JAMP can record:

- sensor observations;
- operating states;
- error codes;
- timestamps;
- network events;
- maintenance events;
- intervention history;
- diagnostic evidence.

It can then investigate questions such as:

**“Why did the device stop?”**

without converting an unsupported hypothesis into a causal conclusion.

A physical-system result follows the same JAMP epistemic rule as software experiments:

**observe → preserve evidence → compare → test → expose conflict → conclude only when the evidence supports the conclusion.**

## 4. Product architecture

The intended separation is:

```
                    JAMP DOMAIN PRODUCTS
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   Browser Extension   Research UI       Engineering UI
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                    JAMP Adapter API
                           │
             ┌─────────────┴─────────────┐
             │                           │
       AI / Search Sensors        External Sources
             │                           │
             └─────────────┬─────────────┘
                           │
                 JAMP Evidence Layer
                           │
       Evidence → Provenance → Conflict → Replay
                           │
                    Deterministic Core
                           │
                     Frozen Core
```

The browser, AI model, search provider or UI is replaceable.

The evidence history is the durable asset.

## 5. Commercialization direction

The first commercial surface can be a browser extension because it has a low integration barrier and can reach users without requiring them to replace their existing browser.

A possible progression is:

### Stage A — Free research extension

Core actions:

- verify selected text;
- inspect sources;
- create an evidence record;
- show conflicts;
- save a research session.

### Stage B — Pro research

Possible capabilities:

- larger research jobs;
- persistent evidence graphs;
- replay;
- multi-source comparison;
- multi-model verification;
- exportable evidence packages.

### Stage C — Team / Research

Possible capabilities:

- shared evidence spaces;
- provenance and audit history;
- organization policies;
- reproducible research workflows;
- API access;
- team collaboration.

### Stage D — Enterprise / API

Possible capabilities:

- programmatic evidence verification;
- domain-specific adapters;
- internal knowledge integration;
- compliance/audit workflows;
- controlled deployment;
- organization-wide evidence infrastructure.

Pricing and packaging are product hypotheses and must be validated experimentally with real users.

## 6. What JAMP should not become

JAMP should not become:

- another general-purpose chatbot;
- a model provider;
- a system that hides uncertainty behind a polished answer;
- a majority-vote truth engine;
- a mechanism that silently changes evidence history;
- a browser fork whose core rendering engine becomes coupled to JAMP;
- a collection of application-specific hacks inside the Frozen Core.

The durable boundary is:

**AI may generate observations. JAMP determines what evidence exists and what remains unresolved.**

## 7. Near-term implementation direction

The first product prototype should be implemented outside the Frozen Core.

Recommended structure:

```
jamp-browser/
├── extension/
│   ├── manifest.json
│   ├── background/
│   ├── content/
│   ├── sidepanel/
│   └── popup/
├── jamp-adapter/
├── evidence-ui/
└── README.md
```

The first vertical slice should be deliberately small:

**Select text → Verify with JAMP → collect observations → preserve sources/provenance → display evidence state.**

Only after this path is reproducible should broader features such as evidence graphs, multi-model federation, replay and paid plans be added.

## 8. Strategic identity

JAMP is best understood as **evidence infrastructure for AI-era research and decision-support systems**.

The strategic opportunity is not to build a model that users must trust.

It is to build infrastructure in which:

- models can be wrong;
- sources can conflict;
- experiments can fail;
- evidence can remain incomplete;

and the system still preserves an explicit, inspectable history of what was observed, what was tested, what was supported, what conflicted, and what remains unknown.

This document describes product direction. It does not modify or weaken the Frozen Core contracts.
