export type ProviderStatus = "ONLINE" | "DEGRADED" | "OFFLINE" | "NOT_CONNECTED" | "UNKNOWN";

export interface ProviderEvidence {
  summary: string;
  observedAt?: string;
  referenceLabel: string;
  referenceUrl?: string;
  artifactId?: string;
}

export interface ProviderRecord {
  id: string;
  name: string;
  status: ProviderStatus;
  description: string;
  evidence: ProviderEvidence;
}

export const PROVIDER_STATUS_LABELS: Record<ProviderStatus, string> = {
  ONLINE: "ONLINE",
  DEGRADED: "DEGRADED",
  OFFLINE: "OFFLINE",
  NOT_CONNECTED: "NOT_CONNECTED",
  UNKNOWN: "UNKNOWN",
};
