"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, read, write } from "../../lib/api";
import { useSession } from "../session-provider";
import LessonTutor from "../../features/lesson-tutor";

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

type Level = { id: string; ordinal: number; title: string; lessons: { id: string; title: string; version: number }[] };
type LevelStatus = { level_id: string; unlocked: boolean; all_lessons_completed: boolean; exam_case_count: number; passed_case_count: number };
type LearningPath = { lessons: Progress[]; next_action: string; level_statuses?: LevelStatus[] };

export default function LearningPage() {
  const { session } = useSession();
  // Preserve drafts across refreshes of the same identity, never across accounts.
  return <LearningWorkspace key={session ? `${session.user.id}:${session.user.role}:${session.user.status}` : "guest"} />;
}

function LearningWorkspace() {
  const [lessonId, setLessonId] = useState("15000000-0000-4000-8000-000000000101");
  const [levels, setLevels] = useState<Level[]>([]);
  const [allProgress, setAllProgress] = useState<Progress[]>([]);
  const [levelStatuses, setLevelStatuses] = useState<LevelStatus[]>([]);
  const { session, loading: sessionLoading } = useSession();
  const userId = session?.user.id;
  const lessonGeneration = useRef(0);
  const examGeneration = useRef(0);
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [active, setActive] = useState(0);
  const [revealedStep, setRevealedStep] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [examResult, setExamResult] = useState<ExamResult | null>(null);
  const [examReady, setExamReady] = useState(false);
  const [examRefreshing, setExamRefreshing] = useState(false);
  const [examError, setExamError] = useState("");
  const [evidence, setEvidence] = useState<string[]>([]);
  const [severity, setSeverity] = useState("medium");
  const [disposition, setDisposition] = useState("undetermined");
  const [reason, setReason] = useState("");

  const load = useCallback(async () => {
    if (!userId) { setLoading(false); return; }
    const request = ++lessonGeneration.current;
    setLoading(true); setError("");
    try {
      const [lessonData, pathData, catalog] = await Promise.all([
        read<Lesson>(`/lessons/${lessonId}`),
        read<LearningPath>("/me/learning-path"),
        read<{ levels: Level[] }>("/learning-path"),
      ]);
      if (request !== lessonGeneration.current) return;
      setLevels(catalog.levels); setAllProgress(pathData.lessons);
      setLevelStatuses(pathData.level_statuses ?? []);
      setLesson(lessonData);
      const saved = pathData.lessons.find((item) => item.lesson_id === lessonId);
      setProgress(saved ?? { lesson_id: lessonId, lesson_version: lessonData.version, completed_steps: [], completed_at: null, version: 0 });
      setActive(saved?.completed_steps.length ?? 0);
    } catch (cause) {
      if (request !== lessonGeneration.current) return;
      if (cause instanceof ApiError && [401, 403, 404].includes(cause.status)) {
        setLesson(null); setProgress(null);
      }
      setError(cause instanceof ApiError && cause.status === 401 ? "เซสชันหมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง" : cause instanceof ApiError && cause.status === 404 ? "บทเรียนนี้ยังไม่เปิดให้บัญชีคุณ กรุณาเรียนและสอบระดับก่อนหน้าให้ผ่านก่อน" : "โหลดบทเรียนไม่สำเร็จ กรุณาลองใหม่");
    } finally { if (request === lessonGeneration.current) setLoading(false); }
  }, [userId, lessonId]);

  const refreshExam = useCallback(async () => {
    if (!userId) return;
    const request = ++examGeneration.current;
    setExamRefreshing(true);
    try {
      const currentAttempt = await read<Attempt>("/exam/attempts/active").catch((cause) => {
        if (cause instanceof ApiError && cause.status === 404) return null;
        throw cause;
      });
      const result = currentAttempt && currentAttempt.status !== "in_progress"
        ? await read<ExamResult>(`/exam/attempts/${currentAttempt.id}/result`)
        : await read<ExamResult>("/exam/attempts/latest/result").catch((cause) => {
          if (cause instanceof ApiError && cause.status === 404) return null;
          throw cause;
        });
      if (request !== examGeneration.current) return;
      setAttempt(currentAttempt?.status === "in_progress" ? currentAttempt : null);
      setExamResult(result); setExamReady(true); setExamError("");
    } catch (cause) {
      if (request !== examGeneration.current) return;
      setExamError(cause instanceof ApiError && cause.status === 401
        ? "เซสชันหมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง"
        : "ตรวจสถานะสอบไม่สำเร็จ บทเรียนยังอ่านได้ แต่ยังใช้ AI หรือเริ่มสอบไม่ได้ กรุณาตรวจสถานะอีกครั้ง");
    } finally { if (request === examGeneration.current) setExamRefreshing(false); }
  }, [userId]);

  useEffect(() => {
    let active = true;
    const generation = lessonGeneration;
    if (!sessionLoading) {
      void Promise.resolve().then(() => {
        if (active) void load();
      });
    }
    return () => { active = false; ++generation.current; };
  }, [load, sessionLoading]);

  useEffect(() => {
    let active = true;
    const generation = examGeneration;
    const refresh = () => {
      if (active && !sessionLoading && document.visibilityState === "visible") void refreshExam();
    };
    void Promise.resolve().then(refresh);
    window.addEventListener("focus", refresh);
    const timer = window.setInterval(refresh, 60000);
    return () => {
      active = false; ++generation.current;
      window.removeEventListener("focus", refresh); window.clearInterval(timer);
    };
  }, [refreshExam, sessionLoading]);

  const attemptId = attempt?.id;
  const attemptStatus = attempt?.status;
  useEffect(() => {
    if (!attemptId || attemptStatus !== "in_progress") return;
    let pending = false;
    let active = true;
    const refresh = async () => {
      if (pending || document.visibilityState !== "visible") return;
      pending = true;
      const request = examGeneration.current;
      try {
        const result = await read<Attempt>(`/exam/attempts/${attemptId}`);
        if (active && request === examGeneration.current) setAttempt(result);
      }
      catch { /* Preserve the current attempt view; explicit actions surface write errors. */ }
      finally { pending = false; }
    };
    const timer = window.setInterval(() => void refresh(), 2500);
    return () => { active = false; window.clearInterval(timer); };
  }, [attemptId, attemptStatus]);

  async function completeStep() {
    if (!lesson || !progress || missingPrerequisite || active >= lesson.steps.length || saving || loading || revealedStep !== lesson.steps[active].id) return;
    setSaving(true); setError("");
    try {
      const step = lesson.steps[active];
      const saved = await write<Progress>(`/lessons/${lessonId}/steps/${step.id}/complete`, { expected_version: progress.version });
      setProgress(saved); setActive(saved.completed_steps.length); setRevealedStep(null);
    } catch (cause) {
      const message = cause instanceof ApiError && cause.code === "PREVIOUS_LESSON_REQUIRED"
        ? "ต้องจบบทเรียนก่อนหน้าให้สมบูรณ์ก่อน จึงจะบันทึกขั้นของบทนี้ได้"
        : cause instanceof ApiError && cause.status === 409
          ? "ความคืบหน้ามีการเปลี่ยนจากอีกหน้าต่าง โหลดข้อมูลล่าสุดแล้ว"
        : "บันทึกขั้นเรียนไม่สำเร็จ กรุณาลองใหม่";
      await load();
      setError(message);
    } finally { setSaving(false); }
  }

  async function completeLesson() {
    if (!progress || missingPrerequisite || saving || loading) return;
    setSaving(true); setError("");
    try {
      const saved = await write<Progress>(`/lessons/${lessonId}/complete`, { expected_version: progress.version });
      setProgress(saved); setAllProgress((items) => [...items.filter((item) => item.lesson_id !== saved.lesson_id), saved]);
      const path = await read<LearningPath>("/me/learning-path");
      setAllProgress(path.lessons); setLevelStatuses(path.level_statuses ?? []);
    } catch (cause) {
      const message = cause instanceof ApiError && cause.code === "PREVIOUS_LESSON_REQUIRED"
        ? "ต้องจบบทเรียนก่อนหน้าให้สมบูรณ์ก่อน จึงจะจบบทนี้ได้"
        : cause instanceof ApiError && cause.status === 409
          ? "ความคืบหน้ามีการเปลี่ยนจากอีกหน้าต่าง โหลดข้อมูลล่าสุดแล้ว"
        : "ยืนยันการจบบทเรียนไม่สำเร็จ กรุณาลองใหม่";
      await load();
      setError(message);
    } finally { setSaving(false); }
  }

  async function startExam() {
    if (!progress || saving || loading || !examReady || examRefreshing || examError) return;
    setSaving(true); setError("");
    try {
      const firstLesson = levels.find((level) => level.id === lesson?.level_id)?.lessons[0]?.id;
      const firstProgress = allProgress.find((item) => item.lesson_id === firstLesson);
      const result = await write<Attempt>(`/learning/levels/${lesson?.level_id}/attempts`, { expected_progress_version: firstProgress?.version ?? progress.version }, { idempotencyKey: crypto.randomUUID() });
      ++examGeneration.current; setExamRefreshing(false); setExamError("");
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
      ++examGeneration.current; setExamRefreshing(false); setExamError("");
      setExamResult(result); setAttempt(null);
    } catch (cause) {
      setError(cause instanceof ApiError && cause.status === 409 ? "ข้อสอบเปลี่ยนสถานะแล้ว โหลดหน้าซ้ำเพื่อดูสถานะล่าสุด" : "ส่งข้อสอบไม่สำเร็จ กรุณาลองใหม่");
    } finally { setSaving(false); }
  }

  const currentLevel = levels.find((item) => item.id === lesson?.level_id);
  const lessonIndex = currentLevel?.lessons.findIndex((item) => item.id === lessonId) ?? -1;
  const missingPrerequisite = lessonIndex > 0 ? currentLevel?.lessons.slice(0, lessonIndex).find((item) =>
    !allProgress.some((saved) => saved.lesson_id === item.id && saved.lesson_version === item.version && saved.completed_at)
  ) : undefined;
  const currentLevelStatus = levelStatuses.find((item) => item.level_id === lesson?.level_id);
  const allLessonsCompleted = currentLevelStatus?.all_lessons_completed ?? (
    !!currentLevel?.lessons.length && currentLevel.lessons.every((item) => allProgress.some((p) => p.lesson_id === item.id && p.lesson_version === item.version && p.completed_at))
  );
  const levelExamComplete = !!currentLevelStatus?.exam_case_count && currentLevelStatus.passed_case_count >= currentLevelStatus.exam_case_count;
  const waitingForReview = !!examResult && ["submitted", "needs_review"].includes(examResult.status);
  const canStartExam = allLessonsCompleted && !attempt && !waitingForReview && !levelExamComplete && !saving && !loading && examReady && !examRefreshing && !examError;

  return <main className="account-page learning-page">
    <p className="eyebrow">เรียน → ฝึก → สอบ</p>
    <h1>เส้นทางเรียนรู้ SOC</h1>
    <p>เริ่มจากอ่าน HTTP request และ response ทีละจุด ความคืบหน้าบันทึกกับบัญชีของคุณบน server</p>
    <p>บทเรียนและความคืบหน้าอ่านจากฐานข้อมูล ไม่ใช้ไฟล์ใน browser เป็นผลการเรียน</p>
    <div className="demo-actions"><Link className="button button-secondary" href="/practice">ฝึกอ่านหลักฐานรวม</Link><Link href="/knowledge-check">ทบทวนข้อเขียน 10 ข้อต่อระดับ</Link><a href="#practical-exam">ไปข้อสอบภาคปฏิบัติ</a></div>
    <section className="learning-card" aria-labelledby="play-flow-title"><h2 id="play-flow-title">เริ่มเล่นตามลำดับนี้</h2><ol>
      <li>เรียน: กดดูหลักฐาน อ่านข้อจำกัด แล้วบันทึกขั้นเรียนให้ครบทุกบทของระดับ</li>
      <li>ฝึก: เลือกเคส ส่งข้อสรุป และอ่าน feedback สีเขียว/แดงจากกฎอ้างอิง ไม่ใช่ผล AI</li>
      <li>Simulation: ไปสถานการณ์ฝึกเพื่ออ่าน event และฝึกสร้าง ticket/note ก่อนจบรอบ</li>
      <li>สอบ: เริ่มเป็นลำดับสุดท้าย ไม่มีผู้ช่วย AI ระหว่างสอบ ผลรอตรวจจน Instructor ประเมิน</li>
    </ol><p>ข้อเขียน 10 ข้อเป็นการทบทวนแยก ยังไม่ใช้แทนข้อสอบเลื่อนระดับ ดูสถานะการเปิดใช้ Dify ในส่วนผู้ช่วยสอนด้านล่าง</p></section>
    <section className="learning-card" id="practical-exam" aria-labelledby="practical-exam-title"><h2 id="practical-exam-title">สอบภาคปฏิบัติและการเลื่อนระดับ</h2>
      {session && !examReady && !examError && <p role="status">กำลังตรวจสถานะสอบ…</p>}
      {session && examError && <p role="alert">{examError}</p>}
      {!session ? <p>เข้าสู่ระบบและเรียนให้ครบก่อนเริ่มสอบ</p> : !lesson ? <p>เลือกบทเรียนที่เปิดให้บัญชีคุณเพื่อดูสถานะระดับ</p> : <>
        <p>ระดับที่เลือก: {currentLevel?.title ?? "กำลังโหลด"}</p>
        {currentLevelStatus && <p>ผ่านเคสสอบ {currentLevelStatus.passed_case_count} / {currentLevelStatus.exam_case_count} เคส</p>}
        <p>ต้องจบบทเรียนทุกบทของระดับก่อนเริ่ม ผลข้อเขียนและแบบฝึกไม่ใช่การสอบผ่าน ระหว่างสอบไม่มีผู้ช่วย AI</p>
        {levelExamComplete ? <p>ผ่านเคสสอบครบระดับนี้แล้ว</p> : <><button disabled={!canStartExam} onClick={() => void startExam()}>{saving ? "กำลังเตรียมข้อสอบ…" : examResult?.status === "passed" ? "เริ่มเคสสอบถัดไป" : examResult ? "เริ่ม attempt ถัดไป" : "เริ่มข้อสอบระดับนี้"}</button>
          {!allLessonsCompleted && <p>ยังเริ่มไม่ได้: ต้องจบบทเรียนทุกบทของระดับนี้ก่อน</p>}
          {waitingForReview && <p>ส่งข้อสอบแล้ว รอ Instructor ตรวจ ก่อนเริ่มเคสถัดไป</p>}
          {attempt && <p>มีข้อสอบที่กำลังทำอยู่ อ่านหลักฐานและส่งคำตอบด้านล่างก่อน</p>}
        </>}
        <button className="button-secondary" disabled={saving || loading || examRefreshing} onClick={() => void Promise.all([load(), refreshExam()])}>ตรวจผลและสิทธิ์ล่าสุด</button>
      </>}
    </section>
    {levels.length > 0 && <section className="learning-card"><h2>เลือกบทเรียน</h2><label>บทเรียนในฐานข้อมูล<select value={lessonId} disabled={saving} onChange={(event) => { setLesson(null); setProgress(null); setRevealedStep(null); setLessonId(event.target.value); }}>
      {levels.map((level) => <optgroup key={level.id} label={`ระดับ ${level.ordinal}: ${level.title}`}>{level.lessons.map((item) => <option key={item.id} value={item.id}>{item.title}{allProgress.some((p) => p.lesson_id === item.id && p.completed_at) ? " · เรียนแล้ว" : ""}</option>)}</optgroup>)}
    </select></label><p>ต้องเรียนตามลำดับ ระดับกลาง/ชำนาญเปิดเมื่อสอบผ่านระดับก่อนหน้าตามสิทธิ์ฝั่ง server</p></section>}
    {!sessionLoading && !session && <section className="learning-card" aria-labelledby="login-required"><h2 id="login-required">เข้าสู่ระบบเพื่ออ่านบทเรียน</h2><p>ยังไม่มีบัญชีใช่ไหม? ลองอ่าน request ตัวอย่างได้ก่อนโดยไม่บันทึกคะแนน บทเรียนและความคืบหน้าจริงต้องใช้บัญชี</p><div className="demo-actions"><Link className="button" href="/demo">ลองข้อมูลตัวอย่าง</Link><Link className="button button-secondary" href="/login">เข้าสู่ระบบ</Link></div></section>}
    {session && loading && <p role="status">{lesson ? "กำลังอัปเดตความคืบหน้า…" : "กำลังโหลดบทเรียนและความคืบหน้า…"}</p>}
    {session && error && <p role="alert">{error} <button className="button-secondary" onClick={() => void load()}>โหลดใหม่</button></p>}
    {session && lesson && progress && <>
      {missingPrerequisite && <section className="learning-card" role="status">
        <h2>ต้องจบบทเรียนก่อนหน้า</h2>
        <p>จบ “{missingPrerequisite.title}” ให้สมบูรณ์ก่อน จึงจะบันทึกขั้นของบทนี้ได้ การบันทึกครบทุกขั้นยังต้องกด “จบบทเรียนและบันทึก” อีกครั้ง</p>
        <button type="button" onClick={() => { setLesson(null); setProgress(null); setRevealedStep(null); setLessonId(missingPrerequisite.id); }}>กลับไปจบบทเรียนก่อนหน้า</button>
      </section>}
      <section className="learning-card">
        <p className="eyebrow">บทเรียน · เวอร์ชัน {lesson.version}</p>
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
        <button disabled={saving || loading || Boolean(missingPrerequisite) || revealedStep !== lesson.steps[active].id} onClick={() => void completeStep()}>{saving ? "กำลังบันทึก…" : "เข้าใจแล้ว บันทึกขั้นนี้"}</button>
      </section> : <section className="learning-card" aria-live="polite">
        <h2>{progress.completed_at ? "จบบทเรียนแล้ว" : "ครบทุกขั้นแล้ว"}</h2>
        {progress.completed_at ? <p>ความคืบหน้าถูกบันทึกแล้ว กลับมาทบทวนได้ทุกเมื่อ</p> : <><p>ยืนยันการจบบทเรียนเพื่อบันทึก lesson completion</p><button disabled={saving || loading || Boolean(missingPrerequisite)} onClick={() => void completeLesson()}>{saving ? "กำลังบันทึก…" : "จบบทเรียนและบันทึก"}</button></>}
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
    {session && levels.length > 0 && <LessonTutor lessonId={lessonId}
      examActive={Boolean(attempt) || waitingForReview}
      accessPending={!examReady || Boolean(examError)}
      lessonReady={Boolean(lesson && progress && lesson.id === lessonId && !loading)} />}
  </main>;
}
