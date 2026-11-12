# Case Study: Black October 2026 — PHP2Shell

## 1. What happened (facts only)

On 21 October 2026, two critical vulnerabilities in the PHP runtime were publicly disclosed as **CVE-2026-109618** and **CVE-2026-109619**, collectively called **PHP2Shell**. The vendor-reported severity is **CVSS v4.0 9.2 (Critical)**. Under affected configurations, the flaws can enable unauthenticated remote code execution; the bugs are in PHP itself, not in a particular application or plugin. Fixed releases were published for supported branches (PHP 8.5.12, 8.4.27, 8.3.36 and 8.2.35). Operators of older branches must check their distribution or vendor for supported backports.

Public reporting described the vulnerabilities as found with AI assistance and as having remained latent for roughly a decade. This describes the discovery context; it does not mean AI alone established exploitability or that every reported exploit attempt succeeded.

Cloudflare reported that observed exploitation **attempts** grew from thousands before disclosure to tens of thousands within 45 minutes, hundreds of thousands within two hours, and millions by 22 October. These are network-observed attempts, not a count of compromised hosts.

Some government and public-sector services were temporarily taken offline while operators assessed exposure or applied fixes. Reporting named services in several European countries; this should not be generalized into a claim that every site in the US, UK, Netherlands, France, Denmark or Finland went offline. The US NSA and UK NCSC issued urgent warnings and patching guidance.

As of 29 October 2026, the public sources reviewed for this case study did **not establish a confirmed mass compromise**. That is not proof that no systems were compromised: exploitation telemetry, suspected targeted incidents and confirmed victim compromise are different evidence classes. The defensible statement is that attempts were widespread, patches were released, and public evidence reviewed here did not establish mass compromise.

Sources:
- [PHP security advisories and release information](https://www.php.net/security)
- [Cloudflare: deploys protections against php2shell](https://blog.cloudflare.com/php-vulnerabilities-waf-protection/)
- [Reuters: government websites go dark after AI-discovered flaw](https://www.reuters.com/world/asia-pacific/eu-agency-warns-websites-may-need-be-taken-offline-php-prepares-patches-2026-10-21/)
- [NSA: critical patches recommended for PHP vulnerabilities](https://www.nsa.gov/press-room/press-releases-statements/press-release-view/article/4630238/nsa-advisory-critical-patches-recommended-for-php-vulnerabilities/)
- [UK NCSC: critical security issue affecting PHP](https://www.ncsc.gov.uk/news/critical-security-issue-affecting-php)

## 2. What JAMP can and cannot do here

### CAN

- Evaluate attributable evidence that a specific host was running a fixed PHP release or vendor backport at a stated time T.
- Check whether evidence supports the claimed sequence: patch receipt, deployment, and—where relevant—restart/replacement of PHP workers.
- Bind source references and their hashes into a UniversalVerdict provenance envelope, so the declared evidence set can be checked for integrity and reproduced under the contract.

These capabilities concern the evidence submitted to JAMP. They do not independently observe a host, establish that logs are truthful, or prove that an entire fleet is patched.

### CANNOT

- Detect PHP2Shell by itself; vulnerability scanners and runtime/security telemetry address detection.
- Prevent exploitation or replace patching, WAF controls, incident response, or vendor guidance.
- Prove the broad claim “the system is secure.” A bounded verdict can only address explicit criteria and a defined evidence/time scope.
- Qualify real-world OpenRouter or provider reliability from this case study.

## 3. UniversalVerdict v0 applied — “host patched against PHP2Shell”

The example below is a **template**, not a verdict about a real host. Placeholder hashes and references must be replaced by collected, immutable evidence before it can be evaluated. Do not sign or label this template VERIFIED as-is.

```json
{
  "spec_ref": {
    "spec_id": "php2shell.host-patched.v0",
    "spec_hash": "sha256:<hash-of-fixed-specification>"
  },
  "criteria_ref": {
    "criteria_id": "php2shell.remediation-criteria.v0",
    "criteria_hash": "sha256:<hash-of-fixed-criteria>"
  },
  "execution_ref": {
    "jamp_verdict_hash": "sha256:<hash-of-original-JampVerdict>",
    "execution_status": "EXECUTE"
  },
  "evidence_refs": [
    {
      "type": "cve_record",
      "ref_hash": "sha256:<hash-of-captured-NVD-record>",
      "source_sha256": "sha256:<sha256-of-captured-source-bytes>"
    },
    {
      "type": "vendor_advisory",
      "ref_hash": "sha256:<hash-of-captured-php.net-advisory>",
      "source_sha256": "sha256:<sha256-of-captured-source-bytes>"
    },
    {
      "type": "version_check",
      "ref_hash": "sha256:<hash-of-php-version-output-with-host-and-timestamp>",
      "source_sha256": "sha256:<sha256-of-original-capture>"
    },
    {
      "type": "patch_receipt",
      "ref_hash": "sha256:<hash-of-dpkg-or-apt-history-entry>",
      "source_sha256": "sha256:<sha256-of-original-log>"
    },
    {
      "type": "deployment_log",
      "ref_hash": "sha256:<hash-of-CI-or-orchestrator-deployment-record>",
      "source_sha256": "sha256:<sha256-of-original-log>"
    },
    {
      "type": "scan_report",
      "ref_hash": "sha256:<hash-of-Trivy-or-Grype-report>",
      "source_sha256": "sha256:<sha256-of-original-report>"
    }
  ],
  "classification": {
    "label": "SECURITY_REMEDIATION_CLAIM",
    "classification_hash": "sha256:<hash-of-classification-payload>"
  },
  "verdict": {
    "result": "INCONCLUSIVE",
    "verdict_hash": "sha256:<hash-of-verdict-payload>"
  },
  "verifier": {
    "version": "uv0.1.0",
    "reproducible": false,
    "aggregation_rule_hash": "sha256:<hash-of-versioned-aggregation-rules>"
  },
  "timestamp": "<UTC-ISO-8601-evaluation-time>"
}
```

The references above are examples of evidence categories, not evidence that a particular host was patched. Capture source bytes or stable immutable records, host identity, timestamps, and collection provenance. A php version output alone may not prove which runtime serves requests; deployment records should identify the actual image/package and the relevant workers. Scanner output is corroborating evidence, not a substitute for runtime and deployment evidence.

### Aggregation rules

The rules below are a case-specific application of the result labels in [UNIVERSAL-VERDICT-CONTRACT-v0.md](UNIVERSAL-VERDICT-CONTRACT-v0.md). They do not redefine the contract schema. Criteria and rule content must be fixed and hashed before evaluating the host.

| Result | Conditions for this claim |
|---|---|
| **VERIFIED** | Evidence is attributable to the named host and time window; the serving runtime is shown to use a fixed release or verified vendor backport; deployment and any required worker restart are evidenced; timestamps and sources are consistent; an independent rerun reproduces the result. |
| **CONTRADICTED** | Reliable, host-attributed evidence shows that the affected runtime was still vulnerable at time T, or contradicts the claimed deployment/restart sequence. |
| **INCONCLUSIVE** | A critical item is missing; evidence is stale or not tied to the serving runtime; host identity or timestamps conflict; source integrity cannot be checked; or a material conflict remains unresolved. |
| **PARTIAL** | The criteria are met for only a declared subset of hosts or components, or patch receipt is evidenced but full deployment/worker replacement is not. State the covered subset explicitly; do not generalize to the fleet. |

An unresolved conflict remains INCONCLUSIVE, in accordance with the contract. A signed payload or matching hash proves integrity of the referenced bytes under the defined mechanism; it does not by itself prove the underlying claim is true.

## 4. Why this matters after Black October

- The volume of newly discovered vulnerabilities can exceed the capacity of humans and organizations to triage, patch, deploy, restart, and independently verify remediation at the same pace.
- As discovery accelerates, value shifts not only to finding a bug but also to demonstrating—host by host and time by time—that remediation actually reached the serving system.
- JAMP's intended role is an **audit/evidence layer**, not a detection, prevention, or patch-management layer.

The case study illustrates a potential evidence workflow. It is not a measurement of JAMP's production effectiveness.

## 5. Evidence boundary

- This is a research document, not a deployed capability or an operational PHP2Shell detector.
- [Universal Verdict v0](UNIVERSAL-VERDICT-CONTRACT-v0.md) is a contract plus data skeleton. The contract explicitly excludes aggregation implementation and API/runtime integration.
- No claim is made that JAMP detected, prevented, or mitigated any exploitation during October 2026.
- This document does not certify that any real host or fleet was patched.
- The related contract work was merged in [PR #468](https://github.com/qwertymarketolog-lab/JAMP/pull/468); API integration is a separate future track.
