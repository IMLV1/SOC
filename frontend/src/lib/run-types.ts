export type RunStatus = "created" | "running" | "paused" | "reviewing" | "completing" | "completed" | "failed";
export type Run = {
  id: string; status: RunStatus; version: number; elapsed_ms: number; duration_ms: number;
  server_time: string; expires_at: string; seed: number; analysis_mode: "mock";
};
export type Event = {
  id: string; run_id: string; release_seq: number; event_time: string; ingested_at: string;
  source: string; asset_id: string | null; username: string | null; src_ip: string | null;
  request: Record<string, unknown> | null; response: Record<string, unknown> | null;
  log: Record<string, unknown>;
};
export type Alert = {
  id: string; run_id: string; severity: "low" | "medium" | "high" | "critical";
  detector_type: "rule" | "anomaly"; detector_version: string; correlation_key: string;
  explanation: string; evidence_ids: string[]; ticket_id: string | null; created_at: string;
};
export type Assessment = {
  id: string; revision: number; author_user_id: string;
  disposition: "true_positive" | "false_positive" | "undetermined";
  reason: string; created_at: string;
};
export type Ticket = {
  id: string; run_id: string; origin: "automatic" | "manual"; correlation_key: string | null;
  title: string; severity: "low" | "medium" | "high" | "critical";
  human_severity_override: boolean; status: "open" | "investigating" | "resolved" | "closed";
  version: number; evidence_ids: string[]; latest_assessment: Assessment | null;
  deleted_at: string | null; created_at: string; updated_at: string;
};
export type Note = {
  id: string; ticket_id: string; owner_user_id: string; body: string; version: number;
  evidence_ids: string[]; deleted_at: string | null; created_at: string; updated_at: string;
};
export type Analysis = {
  id: string; run_id: string; retry_of: string | null; mode: "mock"; model_id: string;
  prompt_version: string; status: "queued" | "running" | "succeeded" | "failed" |
    "invalid_output" | "quota_exceeded" | "timed_out" | "cancelled";
  version: number; evidence_ids: string[];
  result: { summary: string; observed_impact: string; potential_impact: string;
    suggested_severity: { level: string; reason: string }; confidence: { level: string; reason: string };
    hypotheses: { text: string; evidence_refs: string[] }[];
    unknowns: string[]; recommended_checks: string[]; evidence_refs: string[] } | null;
  error_code: string | null; usage: Record<string, unknown> | null;
  created_at: string; finished_at: string | null;
};
