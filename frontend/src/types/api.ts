/**
 * Type declarations for the authenticated BFF proxy to POST /v1/verify_text.
 * These types document the observed backend contract; runtime JSON remains untrusted.
 */

export type ClaimVerdict = "VERIFIED" | "CONTRADICTED" | "INCONCLUSIVE";

export type VerifyTextStatus =
  | "COMPLETE_VERIFICATION"
  | "PARTIAL_VERIFICATION"
  | "NO_CLAIMS";

export interface VerifyTextRequest {
  text: string;
  tolerance_pct?: number;
}

export interface VerifyTextEvidence {
  source: string;
  url: string | null;
  status_code: number | null;
  body_complete: boolean | null;
  raw_body_base64: string | null;
  actual_value: number | string | null;
  timestamp_utc: string;
  timestamp_kind: "JAMP_CAPTURE_TIME";
  age_seconds: number;
  age_basis: string;
  source_timestamp_utc: string | null;
  raw_sha256: string | null;
}

export interface VerifiedClaim {
  claim_id: string;
  raw_text: string;
  type: string;
  extracted_value: number | string | null;
  unit: string;
  verdict: ClaimVerdict;
  reason: string | null;
  evidence: VerifyTextEvidence[];
  trace_id: string;
}

export interface VerifyTextProviderError {
  provider: string;
  status: string;
  message: string;
}

export interface VerifyTextResponse {
  status: VerifyTextStatus;
  system_warnings: string[];
  claims: VerifiedClaim[];
  provider_errors: VerifyTextProviderError[];
  trace_id: string;
  verification_mode?: "DIRECT_E4_NO_E2";
}

export interface VerifyTextApiError {
  detail: string;
}
