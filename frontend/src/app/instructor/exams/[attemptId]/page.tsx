"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, read, write } from "../../../../lib/api";
import { useSession } from "../../../session-provider";

type ExamEvent = { id: string; release_seq: number; event_time: string; source: string; asset_id: string | null; username: string | null; src_ip: string | null; request: Record<string, unknown> | null; response: Record<string, unknown> | null; log: Record<string, unknown> };
type ReviewCase = { attempt: { id: string; status: string; version: number }; events: ExamEvent[]; answer: { evidence_event_ids: string[]; severity: string; disposition: string; reason: string }; private_truth: { expectedEvidenceKeys: string[]; expectedSeverity: string; expectedDisposition: string; criterionGuidance: Record<string, string> } };
type Result = { attempt_id: string; status: string; score: number | null; maximum: number; criteria: { key: string; score: number; maximum: number; feedback: string }[] };

export default function InstructorExamReviewPage() {
  const params = useParams<{ attemptId: string }>();
  const { session, loading } = useSession();
  const [item, setItem] = useState<ReviewCase | null>(null);
  const [scores, setScores] = useState({ analysis: 1, reasoning: 1 });
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (session?.user.role === "instructor") read<ReviewCase>(`/admin/exam-attempts/${params.attemptId}`).then(setItem).catch((cause) => setError(cause instanceof ApiError && cause.status === 401 ? "เซสชันหมดอายุ" : "โหลดข้อสอบไม่สำเร็จ หรือไม่มีสิทธิ์ใน assignment นี้")); }, [params.attemptId, session]);
  async function review() {
    if (!item || !reason.trim() || saving) return;
    setSaving(true); setError("");
    try { setResult(await write<Result>(`/admin/exam-attempts/${item.attempt.id}/review`, { expected_version: item.attempt.version, criterion_scores: scores, reason: reason.trim() })); }
    catch (cause) { setError(cause instanceof ApiError && cause.status === 409 ? "มีผู้ตรวจหรือข้อมูลอื่นแก้ผลแล้ว โหลดข้อมูลใหม่ก่อน" : "บันทึกผลตรวจไม่สำเร็จ"); }
    finally { setSaving(false); }
  }
  return <main className="run-shell"><p><Link href="/instructor/exams">← รายการข้อสอบ</Link></p><h1>ตรวจคำตอบข้อสอบ</h1>
    {loading ? <p role="status">กำลังตรวจบัญชี…</p> : !session ? <p><Link href="/login">เข้าสู่ระบบ</Link></p> : session.user.role !== "instructor" ? <p role="alert">หน้านี้ใช้ได้เฉพาะ Instructor</p> : error && !item ? <p role="alert">{error}</p> : !item ? <p role="status">กำลังโหลด…</p> : <>
      <section className="learning-card">
        <p>สถานะ: {item.attempt.status} · เวอร์ชัน {item.attempt.version}</p>
        <h2>คำตอบผู้เรียน</h2>
        <p>Severity: {item.answer.severity} · Disposition: {item.answer.disposition}</p>
        <p>{item.answer.reason}</p>
        <h3>หลักฐานที่เลือก</h3>
        <ul>{item.answer.evidence_event_ids.map((id) => <li key={id}>{id}</li>)}</ul>
        <h3>ข้อมูลเหตุการณ์</h3>
        {item.events.map((event) => <article key={event.id}>
          <h4>Event {event.release_seq} · {event.source}</h4>
          <pre className="lesson-evidence"><code>{JSON.stringify({ id: event.id, time: event.event_time, asset: event.asset_id, username: event.username, src_ip: event.src_ip, request: event.request, response: event.response, log: event.log }, null, 2)}</code></pre>
        </article>)}
      </section>
      <section className="learning-card"><h2>เฉลยและเกณฑ์</h2><p>Severity: {item.private_truth.expectedSeverity} · Disposition: {item.private_truth.expectedDisposition}</p><p>Evidence keys: {item.private_truth.expectedEvidenceKeys.join(", ")}</p><dl>{Object.entries(item.private_truth.criterionGuidance).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl></section>
      {item.attempt.status === "needs_review" && <section className="learning-card"><h2>ให้คะแนนการวิเคราะห์</h2>{(["analysis", "reasoning"] as const).map((key) => <label key={key}>{key}<select value={scores[key]} onChange={(event) => setScores((current) => ({ ...current, [key]: Number(event.target.value) }))}><option value={0}>0 · ยังไม่เป็นไปตามเกณฑ์</option><option value={1}>1 · ทำได้บางส่วน</option><option value={2}>2 · ทำได้ตามเกณฑ์</option></select></label>)}<label>เหตุผลการตรวจ<textarea value={reason} maxLength={2000} onChange={(event) => setReason(event.target.value)} rows={4} /></label><button disabled={saving || !reason.trim()} onClick={() => void review()}>{saving ? "กำลังบันทึก…" : "บันทึกผลตรวจ"}</button></section>}
      {error && <p role="alert">{error}</p>}{result && <section className="learning-card" aria-live="polite"><h2>ผล: {result.status}</h2>{result.score !== null && <p>คะแนน {result.score}/{result.maximum}</p>}{result.criteria.map((criterion) => <p key={criterion.key}>{criterion.key}: {criterion.feedback}</p>)}</section>}
    </>}
  </main>;
}
