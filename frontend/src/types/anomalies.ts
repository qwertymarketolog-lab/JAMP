export type AnomalyStatus = "INCONCLUSIVE" | "SUSPICIOUS";

export interface AnomalyRecord {
  verdict_id: string;
  status: AnomalyStatus;
  package: string | null;
  created_at: string;
  code_hash: string;
}

export interface AnomalyVerdictListResponse {
  items: AnomalyRecord[];
  limit: number;
  offset: number;
  total: number;
}

export interface AnomalyStatsResponse {
  inconclusive: number;
}

export interface DashboardSessionResponse {
  authenticated: true;
  org_id: string;
  session_expires_at: string;
}
