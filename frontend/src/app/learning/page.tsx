"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ApiError, read, write } from "../../lib/api";
import { useSession } from "../session-provider";

type Lesson = {
  id: string;
  level_id: string;
  version: number;
  title: string;
  steps: { id: string; title: string; target: string; explanation: string; limitation: string }[];
};
type Progress = { lesson_id: string; lesson_version: number; completed_steps: string[]; completed_at: string | null; version: number };
type ExamEvent = { id: string; release_seq: number; event_time: string; source: string; asset_id: string | null; username: string | null; src_ip: string | null; request: Record<string, unknown> | null; response: Record<string, unknown> | null; log: Record<string, unknown> };
type Attempt = { id: string; level_id: string; status: string; version: number; expires_at: string; events: ExamEvent[]; answer: { evidence_event_ids: string[]; severity: string; disposition: string; reason: string } | null };
type ExamResult = { attempt_id: string; status: string; score: number | null; maximum: number; criteria: { key: string; score: number; maximum: number; feedback: string }[] };

const lessonId = "15000000-0000-4000-8000-000000000101";

export default function LearningPage() {
  const { session, loading: sessionLoading } = useSession();
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [active, setActive] = useState(0);
  const [revealedStep, setRevealedStep] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [examResult, setExamResult] = useState<ExamResult | null>(null);
  const [evidence, setEvidence] = useState<string[]>([]);
  const [severity, setSeverity] = useState("medium");
  const [disposition, setDisposition] = useState("undetermined");
  const [reason, setReason] = useState("");

  const load = useCallback(async () => {
    if (!session) { setLoading(false); return; }
    setLoading(true); setError("");
    try {
      const [lessonData, pathData] = await Promise.all([
        read<Lesson>(`/lessons/${lessonId}`),
        read<{ lessons: Progress[]; next_action: string }>("/me/learning-path"),
      ]);
      setLesson(lessonData);
      const saved = pathData.lessons.find((item) => item.lesson_id === lessonId);
      setProgress(saved ?? { lesson_id: lessonId, lesson_version: lessonData.version, completed_steps: [], completed_at: null, version: 0 });
      setActive(saved?.completed_steps.length ?? 0);
      const currentAttempt = await read<Attempt>("/exam/attempts/active").catch((cause) => {
        if (cause instanceof ApiError && cause.status === 404) return null;
        throw cause;
      });
      setAttempt(currentAttempt?.status === "in_progress" ? currentAttempt : null);
      if (currentAttempt && currentAttempt.status !== "in_progress") {
        setExamResult(await read<ExamResult>(`/exam/attempts/${currentAttempt.id}/result`));
      } else {
        const latestResult = await read<ExamResult>("/exam/attempts/latest/result").catch((cause) => {
          if (cause instanceof ApiError && cause.status === 404) return null;
          throw cause;
        });
        setExamResult(latestResult);
      }
    } catch (cause) {
      setError(cause instanceof ApiError && cause.status === 401 ? "เซสชันหมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง" : "โหลดบทเรียนไม่สำเร็จ กรุณาลองใหม่");
    } finally { setLoading(false); }
  }, [session]);

  useEffect(() => {
    let active = true;
    if (!sessionLoading) {
      void Promise.resolve().then(() => {
        if (active) void load();
      });
    }
    return () => { active = false; };
  }, [load, sessionLoading]);

  const attemptId = attempt?.id;
  const attemptStatus = attempt?.status;
  useEffect(() => {
    if (!attemptId || attemptStatus !== "in_progress") return;
    let pending = false;
    const refresh = async () => {
      if (pending || document.visibilityState !== "visible") return;
      pending = true;
      try { setAttempt(await read<Attempt>(`/exam/attempts/${attemptId}`)); }
      catch { /* Preserve the current attempt view; explicit actions surface write errors. */ }
      finally { pending = false; }
    };
    const timer = window.setInterval(() => void refresh(), 2500);
    return () => window.clearInterval(timer);
  }, [attemptId, attemptStatus]);

  async function completeStep() {
    if (!lesson || !progress || active >= lesson.steps.length || saving || revealedStep !== lesson.steps[active].id) return;
    setSaving(true); setError("");
    try {
      const step = lesson.steps[active];
      const saved = await write<Progress>(`/lessons/${lessonId}/steps/${step.id}/complete`, { expected_version: progress.version });
      setProgress(saved); setActive(saved.completed_steps.length); setRevealedStep(null);
    } catch (cause) {
      const message = cause instanceof ApiError && cause.status === 409
        ? "ความคืบหน้ามีการเปลี่ยนจากอีกหน้าต่าง โหลดข้อมูลล่าสุดแล้ว"
        : "บันทึกขั้นเรียนไม่สำเร็จ กรุณาลองใหม่";
      await load();
      setError(message);
    } finally { setSaving(false); }
  }

  async function completeLesson() {
    if (!progress || saving) return;
    setSaving(true); setError("");
    try {
      const saved = await write<Progress>(`/lessons/${lessonId}/complete`, { expected_version: progress.version });
      setProgress(saved);
    } catch (cause) {
      const message = cause instanceof ApiError && cause.status === 409
        ? "ความคืบหน้ามีการเปลี่ยนจากอีกหน้าต่าง โหลดข้อมูลล่าสุดแล้ว"
        : "ยืนยันการจบบทเรียนไม่สำเร็จ กรุณาลองใหม่";
      await load();
      setError(message);
    } finally { setSaving(false); }
  }

  async function startExam() {
    if (!progress || saving) return;
    setSaving(true); setError("");
    try {
      const result = await write<Attempt>(`/learning/levels/${lesson?.level_id}/attempts`, { expected_progress_version: progress.version }, { idempotencyKey: crypto.randomUUID() });
      setExamResult(null); setAttempt(result); setEvidence([]); setReason("");
    } catch (cause) {
      const code = cause instanceof ApiError ? cause.code : "";
      setError(code === "EXAM_COOLDOWN_ACTIVE"
        ? "หลังสอบตก ต้องรอ 1 ชั่วโมงก่อนเริ่ม attempt ถัดไป"
        : code === "EXAM_ATTEMPT_QUOTA_EXCEEDED"
          ? "ใช้โควตาของ case นี้ครบ 3 ครั้งใน 24 ชั่วโมงแล้ว"
          : cause instanceof ApiError && cause.status === 409
            ? "ยังเริ่มข้อสอบไม่ได้ ตรวจว่าบทเรียนเสร็จและไม่มี attempt อื่นค้างอยู่"
            : "เริ่มข้อสอบไม่สำเร็จ กรุณาลองใหม่");
    } finally { setSaving(false); }
  }

  async function submitExam() {
    if (!attempt || saving || !reason.trim() || evidence.length === 0) return;
    setSaving(true); setError("");
    try {
      const result = await write<ExamResult>(`/exam/attempts/${attempt.id}/submit`, { expected_version: attempt.version, evidence_event_ids: evidence, severity, disposition, reason: reason.trim() }, { idempotencyKey: crypto.randomUUID() });
      setExamResult(result); setAttempt(null);
    } catch (cause) {
      setError(cause instanceof ApiError && cause.status === 409 ? "ข้อสอบเปลี่ยนสถานะแล้ว โหลดหน้าซ้ำเพื่อดูสถานะล่าสุด" : "ส่งข้อสอบไม่สำเร็จ กรุณาลองใหม่");
    } finally { setSaving(false); }
  }

  return <main className="account-page learning-page">
    <p className="eyebrow">LEARNING PATH / LEVEL 01</p>
    <h1>เส้นทางเรียนรู้ SOC</h1>
    <p>เริ่มจากอ่าน HTTP request และ response ทีละจุด ความคืบหน้าบันทึกกับบัญชีของคุณบน server</p>
    <p><Link href="/demo/learning">ลองบทเรียนจาก JSON ครบ 3 ระดับ (ไม่บันทึกคะแนน ไม่ใช้ฐานข้อมูล)</Link></p>
    {!sessionLoading && !session && <section className="learning-card" aria-labelledby="login-required"><h2 id="login-required">เข้าสู่ระบบเพื่ออ่านบทเรียน</h2><p>ยังไม่มีบัญชีใช่ไหม? ลองอ่าน request ตัวอย่างได้ก่อนโดยไม่บันทึกคะแนน บทเรียนและความคืบหน้าจริงต้องใช้บัญชี</p><div className="demo-actions"><Link className="button" href="/demo">ลองข้อมูลตัวอย่าง</Link><Link className="button button-secondary" href="/login">เข้าสู่ระบบ</Link></div></section>}
    {session && loading && <p role="status">กำลังโหลดบทเรียนและความคืบหน้า…</p>}
    {session && error && <p role="alert">{error} <button className="button-secondary" onClick={() => void load()}>โหลดใหม่</button></p>}
    {session && lesson && progress && !loading && <>
      <section className="learning-card">
        <p className="eyebrow">บทเรียนตัวอย่าง · เวอร์ชัน {lesson.version}</p>
        <h2>{lesson.title}</h2>
        <p>เรียนแล้ว {progress.completed_steps.length} จาก {lesson.steps.length} ขั้น</p>
        <ol className="lesson-steps">{lesson.steps.map((step, index) => <li key={step.id} aria-current={index === active && active < lesson.steps.length ? "step" : undefined}>
          <span>{step.title}</span>{progress.completed_steps.includes(step.id) ? <span className="lesson-done">บันทึกแล้ว</span> : index === active ? <span>ขั้นปัจจุบัน</span> : <span>ถัดไป</span>}
        </li>)}</ol>
      </section>
      {active < lesson.steps.length ? <section className="learning-card" aria-live="polite">
        <p className="eyebrow">ขั้น {active + 1} / {lesson.steps.length}</p><h2>{lesson.steps[active].title}</h2>
        <p>กดข้อมูลตัวอย่างด้านล่างเพื่ออ่านจุดที่กำลังเรียน แล้วค่อยบันทึกขั้นนี้</p>
        <button className="lesson-target" type="button" aria-expanded={revealedStep === lesson.steps[active].id} onClick={() => setRevealedStep(lesson.steps[active].id)}>
          <span>กดดู: {lesson.steps[active].title}</span><code>{lesson.steps[active].target}</code>
        </button>
        {revealedStep === lesson.steps[active].id && <div className="lesson-explanation"><p>{lesson.steps[active].explanation}</p><p><strong>สิ่งที่ยังสรุปไม่ได้:</strong> {lesson.steps[active].limitation}</p></div>}
        <button disabled={saving || revealedStep !== lesson.steps[active].id} onClick={() => void completeStep()}>{saving ? "กำลังบันทึก…" : "เข้าใจแล้ว บันทึกขั้นนี้"}</button>
      </section> : <section className="learning-card" aria-live="polite">
        <h2>{progress.completed_at ? "จบบทเรียนแล้ว" : "ครบทุกขั้นแล้ว"}</h2>
        {progress.completed_at ? <p>ความคืบหน้าถูกบันทึกแล้ว กลับมาทบทวนได้ทุกเมื่อ</p> : <><p>ยืนยันการจบบทเรียนเพื่อบันทึก lesson completion</p><button disabled={saving} onClick={() => void completeLesson()}>{saving ? "กำลังบันทึก…" : "จบบทเรียนและบันทึก"}</button></>}
        {progress.completed_at && !attempt && (!examResult || ["failed", "expired"].includes(examResult.status)) && <button disabled={saving} onClick={() => void startExam()}>{saving ? "กำลังเตรียมข้อสอบ…" : examResult ? "เริ่ม attempt ถัดไป" : "เริ่มข้อสอบระดับนี้"}</button>}
      </section>}
      {attempt && <section className="learning-card" aria-labelledby="exam-title">
        <p className="eyebrow">ข้อสอบ · หมดเวลา {new Date(attempt.expires_at).toLocaleString("th-TH")}</p><h2 id="exam-title">Investigation case</h2>
        <p>เลือก event ที่ใช้เป็นหลักฐาน แล้วบันทึกข้อสรุปของคุณ คำตอบจะถูกส่งตรวจและแก้ไขไม่ได้</p>
        <ol className="lesson-steps">{attempt.events.map((event) => <li key={event.id} className="exam-event"><label><input type="checkbox" checked={evidence.includes(event.id)} onChange={(change) => setEvidence((current) => change.target.checked ? [...current, event.id] : current.filter((id) => id !== event.id))} /> Event {event.release_seq} · {event.source} · {event.asset_id ?? "ไม่ระบุ asset"}</label><pre className="lesson-evidence"><code>{JSON.stringify({ event_time: event.event_time, username: event.username, src_ip: event.src_ip, request: event.request, response: event.response, log: event.log }, null, 2)}</code></pre></li>)}</ol>
        <label>Severity<select value={severity} onChange={(event) => setSeverity(event.target.value)}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select></label>
        <label>Disposition<select value={disposition} onChange={(event) => setDisposition(event.target.value)}><option value="true_positive">True positive</option><option value="false_positive">False positive</option><option value="undetermined">Undetermined</option></select></label>
        <label>เหตุผลและการวิเคราะห์<textarea value={reason} maxLength={2000} onChange={(event) => setReason(event.target.value)} rows={5} /></label>
        <button disabled={saving || !reason.trim() || evidence.length === 0} onClick={() => void submitExam()}>{saving ? "กำลังส่ง…" : "ส่งข้อสอบ"}</button>
      </section>}
      {examResult && <section className="learning-card" aria-live="polite"><h2>ผลข้อสอบ: {examResult.status}</h2>{examResult.score !== null && <p>คะแนน {examResult.score}/{examResult.maximum}</p>}{examResult.status === "needs_review" && <p>ส่งคำตอบแล้ว รอ Instructor ตรวจ ไม่มีการประเมินผ่านอัตโนมัติ</p>}{examResult.criteria.map((item) => <p key={item.key}><strong>{item.key}:</strong> {item.feedback}</p>)}</section>}
    </>}
  </main>;
}
