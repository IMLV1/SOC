"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ApiError, read, write } from "../../lib/api";
import { useSession } from "../session-provider";
import { WrittenFeedback } from "../../features/written-feedback";

type Question = { id: string; ordinal: number; version: number; prompt: string; category: string };
type Submission = { id: string; level_id: string; status: "needs_review"; created_at: string; questions: Question[]; answers: { question_id: string; answer: string }[] };
type Level = { id: string; title: string; ordinal: number };

export default function KnowledgeCheckPage() {
  const { session, loading: sessionLoading } = useSession();
  const [levels, setLevels] = useState<Level[]>([]);
  const [levelId, setLevelId] = useState("");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [history, setHistory] = useState<Submission[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const requestKey = useRef<{ body: string; key: string } | null>(null);
  const loadedLevel = useRef<string | null>(null);
  useEffect(() => {
    if (!session) return;
    let active = true;
    read<{ levels: Level[] }>("/learning-path").then((data) => { if (active) { setLevels(data.levels); setLevelId((current) => current || data.levels[0]?.id || ""); } }).catch(() => { if (active) { setError("โหลดระดับไม่สำเร็จ"); setLoading(false); } });
    return () => { active = false; };
  }, [session, retry]);
  useEffect(() => {
    if (!session || !levelId) return;
    let active = true;
    Promise.resolve().then(() => { if (active) { setLoading(true); setError(""); setQuestions([]); setHistory([]); } });
    Promise.all([read<Question[]>(`/learning/levels/${levelId}/written-questions`), read<Submission[]>(`/learning/levels/${levelId}/written-submissions`)])
      .then(([items, saved]) => { if (active) {
        setQuestions(items); setHistory(saved);
        if (loadedLevel.current !== levelId) { setAnswers({}); requestKey.current = null; loadedLevel.current = levelId; }
      } })
      .catch((cause) => { if (active) setError(cause instanceof ApiError && cause.status === 409 ? "ต้องเรียนทุกบทของระดับให้ครบ และไม่มีข้อสอบภาคปฏิบัติค้างอยู่" : cause instanceof ApiError && cause.status === 404 ? "ระดับนี้ยังไม่ปลดล็อก" : cause instanceof ApiError && cause.status === 401 ? "เซสชันหมดอายุ กรุณาเข้าสู่ระบบ" : "โหลดคำถามไม่สำเร็จ กรุณาลองใหม่"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [session, levelId, retry]);
  async function submit(event: React.FormEvent) {
    event.preventDefault(); if (busy) return; setBusy(true); setError("");
    const payload = { answers: questions.map((item) => ({ question_id: item.id, answer: answers[item.id]?.trim() ?? "" })) };
    const body = JSON.stringify(payload);
    if (requestKey.current?.body !== body) requestKey.current = { body, key: crypto.randomUUID() };
    try {
      const saved = await write<Submission>(`/learning/levels/${levelId}/written-submissions`, payload, { idempotencyKey: requestKey.current.key });
      setHistory((items) => [saved, ...items.filter((item) => item.id !== saved.id)]); setAnswers({}); requestKey.current = null;
    } catch { setError("ส่งคำตอบไม่สำเร็จ คำตอบของคุณยังอยู่ ลองส่งอีกครั้งได้"); }
    finally { setBusy(false); }
  }
  return <main className="account-page learning-page"><h1>ทบทวนข้อเขียน</h1><p>10 คำถามต่อระดับ ต้องเรียนครบก่อนเปิด คำตอบทั้งชุดบันทึกในฐานข้อมูลและแก้ชุดที่ส่งแล้วไม่ได้ ส่วนข้อความที่ยังไม่ส่งยังไม่บันทึก</p><p>หลังส่งแล้วขอข้อเสนอแนะจาก Dify ได้เมื่อผู้ดูแลเปิดโหมด grade ผลยังไม่ใช่คะแนนสอบหรือการปลดล็อกระดับ</p><div className="demo-actions"><Link href="/learning">เรียนและสอบภาคปฏิบัติ</Link><Link href="/practice">ฝึกอ่านหลักฐาน</Link></div>
    {sessionLoading ? <p role="status">กำลังตรวจบัญชี…</p> : !session ? <Link href="/login">เข้าสู่ระบบเพื่อทำข้อเขียน</Link> : <>
      <label>ระดับ<select value={levelId} disabled={busy} onChange={(event) => { if (!Object.values(answers).some(Boolean) || window.confirm("คำตอบยังไม่ส่ง ต้องการเปลี่ยนระดับหรือไม่?")) setLevelId(event.target.value); }}>{levels.map((level) => <option key={level.id} value={level.id}>{level.ordinal} · {level.title}</option>)}</select></label>
      {loading && <p role="status">กำลังโหลดคำถาม…</p>}{error && <p role="alert">{error} <button disabled={busy} onClick={() => setRetry((value) => value + 1)}>โหลดใหม่</button></p>}
      {!loading && questions.length > 0 && <form className="learning-card" onSubmit={submit}>{questions.map((item) => <label key={item.id}>{item.ordinal}. {item.prompt}<textarea rows={4} required disabled={busy} maxLength={2000} value={answers[item.id] ?? ""} onChange={(event) => setAnswers((current) => ({ ...current, [item.id]: event.target.value }))} /></label>)}<button disabled={busy || questions.some((item) => !answers[item.id]?.trim())}>ส่งคำตอบครบ 10 ข้อ</button></form>}
      <section className="learning-card"><h2>ประวัติที่ส่งแล้ว</h2>{history.length === 0 ? <p>ยังไม่มีคำตอบที่ส่งในระดับนี้</p> : history.map((item) => <WrittenFeedback key={item.id} levelId={levelId} submission={item} />)}</section>
    </>}
  </main>;
}
