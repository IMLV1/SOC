export type CaseSummary = {
  id: string; stable_key: string; level_id: string; level: number;
  category: string; title: string; version: number; available: boolean;
};
export type PracticeDraft = {
  evidence_ids: string[]; severity: "low" | "medium" | "high" | "critical";
  disposition: "true_positive" | "false_positive" | "undetermined"; reason: string;
};
export type PracticeCase = CaseSummary & {
  prompt: string; events: { id: string; time: string; source: string; asset: string;
    username: string; src_ip: string; request: Record<string, unknown> | null;
    response: Record<string, unknown> | null; log: Record<string, unknown> }[];
  draft: PracticeDraft | null; draft_version: number;
  draft_saved_at: string | null;
};
export type PracticeResult = {
  id: string; case_id: string; case_version: number; answer: PracticeDraft; created_at: string;
  feedback: { mode: "deterministic"; classification_correct: boolean; evidence_correct: boolean;
    expected_severity: string; expected_disposition: string; explanation: string; limitation: string;
    reason_review_status: "unavailable"; reason_review_message: string; is_exam_result: false };
};
export const categories: Record<string, string> = {
  authentication: "บัญชีและการเข้าสู่ระบบ", web: "Web request", access: "สิทธิ์การเข้าถึง",
  evidence: "หลักฐานและข้อจำกัด", change: "Change และ scope", data: "การเข้าถึงข้อมูล",
  anomaly: "Anomaly และ baseline", availability: "ความพร้อมใช้งาน",
};
export const blankDraft = (): PracticeDraft => ({ evidence_ids: [], severity: "medium", disposition: "undetermined", reason: "" });
