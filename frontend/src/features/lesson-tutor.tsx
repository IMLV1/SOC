"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, read, write } from "../lib/api";

type Availability = { available: boolean; reason: string | null };
type Question = {
  id: string; lesson_id: string; question: string; status: string; error_code: string | null;
  result: { answer: string; sources: { title: string; excerpt: string; section_ids: string[] }[] } | null;
};
const reasons: Record<string, string> = {
  DIFY_RELEASE_NOT_APPROVED: "รอรับรอง Workflow, แหล่งอ้างอิง และขอบเขตค่าใช้จ่ายก่อนเปิดใช้จริง",
  DIFY_CREDENTIAL_UNAVAILABLE: "ยังตั้งค่า secret ฝั่ง server ไม่ครบ",
  EXAM_ATTEMPT_ACTIVE: "ผู้ช่วย AI ปิดระหว่างมีข้อสอบที่ยังไม่สิ้นสุด",
  AI_QUOTA_EXCEEDED: "ใช้โควตา AI ของบัญชีวันนี้ครบแล้ว",
  DIFY_CITATION_OR_OUTPUT_INVALID: "คำตอบหรือแหล่งอ้างอิงไม่ผ่านการตรวจ จึงยังไม่แสดงคำตอบ",
  DIFY_NO_MATCH: "ไม่พบข้อมูลในคู่มือที่รองรับ กรุณาระบุหัวข้อหรือรายละเอียดคำถามเพิ่มเติม",
  DIFY_PINNED_VERSION_UNAVAILABLE: "แพ็กเกจ Dify ปัจจุบันไม่รองรับการเรียก Workflow แบบล็อกเวอร์ชัน",
  DIFY_WORKFLOW_VERSION_MISMATCH: "Workflow ที่ Publish เปลี่ยนไปจากรุ่นที่อนุมัติ จึงไม่แสดงคำตอบ กรุณาให้ผู้ดูแลตรวจการตั้งค่า",
  DIFY_DISPATCH_OUTCOME_UNKNOWN: "ไม่ทราบผลการเรียกครั้งก่อน ระบบจะไม่ส่งซ้ำอัตโนมัติ",
};

export default function LessonTutor({ lessonId, examActive, accessPending = false, lessonReady = true }: {
  lessonId: string; examActive: boolean; accessPending?: boolean; lessonReady?: boolean;
}) {
  const [availability, setAvailability] = useState<Availability | null>(null);
  const [history, setHistory] = useState<Question[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [retry, setRetry] = useState(0);
  const pendingKey = useRef<{ body: string; key: string } | null>(null);
  const generation = useRef(0);

  useEffect(() => {
    const current = ++generation.current;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;
    let delay = 1500;
    async function load() {
      if (stopped) return;
      if (document.hidden) { timer = setTimeout(load, 5000); return; }
      try {
        const status = await read<Availability>("/tutor/availability");
        if (stopped) return;
        setAvailability(status);
        if (status.reason === "EXAM_ATTEMPT_ACTIVE") { setHistory([]); return; }
        const items = await read<Question[]>("/tutor/questions");
        if (stopped) return;
        setHistory(items); setLoadError(""); delay = 1500;
        if (items.some((item) => ["queued", "running"].includes(item.status))) timer = setTimeout(load, delay);
      } catch (cause) {
        if (stopped) return;
        setLoadError(cause instanceof ApiError && cause.status === 401 ? "บัญชีหมดอายุ กรุณาเข้าสู่ระบบใหม่" : "ตรวจสถานะผู้ช่วย AI ไม่สำเร็จ");
        setAvailability(null); delay = Math.min(delay * 2, 15000);
        if (!(cause instanceof ApiError && cause.status === 401)) timer = setTimeout(load, delay);
      }
    }
    void load();
    return () => { stopped = true; generation.current = current + 1; if (timer) clearTimeout(timer); };
  }, [retry, examActive]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy || !availability?.available || examActive || accessPending || !lessonReady || !question.trim()) return;
    const current = generation.current;
    const payload = { lesson_id: lessonId, question: question.trim() };
    const body = JSON.stringify(payload);
    if (pendingKey.current?.body !== body) pendingKey.current = { body, key: crypto.randomUUID() };
    setBusy(true); setError("");
    try {
      const item = await write<Question>("/tutor/questions", payload, { idempotencyKey: pendingKey.current.key });
      if (current !== generation.current) return;
      setHistory((items) => [item, ...items.filter((old) => old.id !== item.id)]);
      setQuestion(""); pendingKey.current = null; setRetry((value) => value + 1);
    } catch (cause) {
      if (current === generation.current) setError(cause instanceof ApiError ? reasons[cause.code] ?? "ส่งคำถามไม่สำเร็จ เก็บข้อความไว้แล้ว" : "ส่งคำถามไม่สำเร็จ เก็บข้อความไว้แล้ว");
    } finally { setBusy(false); }
  }
  return <section className="learning-card" aria-labelledby="tutor-title">
    <h2 id="tutor-title">ถามผู้ช่วยสอน AI</h2>
    <p>ถามความหมายและวิธีอ่านหลักฐาน ไม่ใช่ผู้ตรวจคะแนน · ใช้ Dify เมื่อ server เปิดให้ใช้งาน</p>
    {examActive ? <p role="status">ผู้ช่วย AI ปิดระหว่างสอบ</p> : accessPending ? <p role="status">กำลังตรวจสิทธิ์ผู้ช่วย AI กรุณารอผลตรวจสถานะสอบ</p> : <>
      {!lessonReady && <p role="status">กำลังโหลดบทเรียนที่เลือก ยังส่งคำถามไม่ได้</p>}
      {!availability && !error && !loadError && <p role="status">กำลังตรวจสถานะผู้ช่วย…</p>}
      {availability && !availability.available && <p role="status">{reasons[availability.reason ?? ""] ?? "ผู้ช่วย AI ยังไม่พร้อมใช้งาน"}</p>}
      {error && <p role="alert">{error}</p>}
      {loadError && <p role="alert">{loadError}</p>}
      <form onSubmit={submit}>
        <label>คำถามเกี่ยวกับบทเรียน<textarea rows={3} maxLength={2000} required value={question} disabled={busy} onChange={(event) => setQuestion(event.target.value)} /></label>
        <p>ไม่ส่งรหัสผ่าน token หรือข้อมูลส่วนบุคคลในคำถาม ข้อความที่ยังไม่ส่งยังไม่บันทึกบน server</p>
        <button disabled={busy || !availability?.available || !lessonReady || !question.trim()}>{busy ? "กำลังส่ง…" : "ส่งคำถาม"}</button>
        <button type="button" disabled={busy} onClick={() => setRetry((value) => value + 1)}>ตรวจสถานะและประวัติล่าสุด</button>
      </form>
      <h3>ประวัติคำถามในบัญชี</h3>
      {history.length === 0 && <p>ยังไม่มีคำถาม หรือยังโหลดประวัติไม่ได้</p>}
      {history.map((item) => <article key={item.id}><h4>{item.question}</h4>
        <p>{["queued", "running"].includes(item.status) ? "กำลังรอประมวลผล" : item.status === "succeeded" ? "ตอบแล้ว · แหล่งอ้างอิงผ่านการตรวจโครงสร้าง ไม่ใช่การรับรองความถูกต้องทุกข้อความ" : reasons[item.error_code ?? ""] ?? "คำตอบยังไม่พร้อม หรือแหล่งความรู้ถูกถอน"}</p>
        {item.result && <><p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{item.result.answer}</p>
          {item.result.sources.map((source, index) => <details key={index}><summary>{source.title} · {source.section_ids.join(", ")}</summary><p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{source.excerpt}</p></details>)}</>}
      </article>)}
    </>}
  </section>;
}
