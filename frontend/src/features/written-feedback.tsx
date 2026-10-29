"use client";

import { useEffect, useState } from "react";
import { ApiError, read, write } from "../lib/api";

type Question = { id: string; ordinal: number; prompt: string };
type Submission = {
  id: string;
  created_at: string;
  questions: Question[];
  answers: { question_id: string; answer: string }[];
};
type Feedback = {
  status: "queued" | "running" | "succeeded" | "needs_review" | "unavailable" | "withdrawn";
  result: { items: { question_id: string; verdict: "supported" | "unsupported" | "insufficient"; explanation: string; section_ids: string[] }[] } | null;
  error_code: string | null;
};

const verdict = {
  supported: "มีข้อมูลรองรับ",
  unsupported: "ข้อมูลไม่รองรับข้อสรุป",
  insufficient: "หลักฐานยังไม่พอ",
};

export function WrittenFeedback({ levelId, submission }: { levelId: string; submission: Submission }) {
  const [open, setOpen] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [loading, setLoading] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [error, setError] = useState("");
  const path = `/learning/levels/${levelId}/written-submissions/${submission.id}/feedback`;

  useEffect(() => {
    if (!open) return;
    let active = true;
    async function refresh() {
      try {
        const value = await read<Feedback>(path);
        if (active) { setFeedback(value); setUnavailable(false); setError(""); }
      } catch (cause) {
        if (active && cause instanceof ApiError && cause.status === 404) setUnavailable(true);
        else if (active) setError("โหลดผลตรวจไม่สำเร็จ");
      }
    }
    void refresh();
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible" && (feedback?.status === "queued" || feedback?.status === "running")) void refresh();
    }, 3000);
    return () => { active = false; window.clearInterval(timer); };
  }, [open, path, feedback?.status]);

  async function requestFeedback() {
    if (loading) return;
    setLoading(true); setError("");
    try {
      setFeedback(await write<Feedback>(path, {}));
      setUnavailable(false);
    } catch (cause) {
      setError(cause instanceof ApiError && cause.code === "DIFY_GRADE_NOT_APPROVED"
        ? "โหมดตรวจคำตอบใน Dify ยังไม่เปิดใช้งาน"
        : cause instanceof ApiError && cause.status === 429
          ? "โควตาคำขอ AI ของวันนี้เต็มแล้ว"
          : "ขอให้ AI ตรวจคำตอบไม่สำเร็จ กรุณาลองใหม่");
    } finally { setLoading(false); }
  }

  return <details onToggle={(event) => setOpen(event.currentTarget.open)}>
    <summary>{new Date(submission.created_at).toLocaleString("th-TH")} · needs_review — รอประเมิน ไม่ใช่สอบผ่าน</summary>
    {submission.questions.map((question) => <section key={question.id}>
      <h3>{question.ordinal}. {question.prompt}</h3>
      <p>{submission.answers.find((answer) => answer.question_id === question.id)?.answer}</p>
    </section>)}
    {open && <section className="learning-card" aria-label="ข้อเสนอแนะจาก AI">
      <h3>ข้อเสนอแนะจาก AI</h3>
      <p>ใช้ Dify Workflow เดียวกับผู้ช่วยสอนในโหมด grade หลังส่งคำตอบแล้ว ผลนี้ไม่ใช่คะแนนสอบหรือการปลดล็อกระดับ</p>
      {unavailable && <button type="button" disabled={loading} onClick={() => void requestFeedback()}>{loading ? "กำลังส่ง…" : "ให้ AI ตรวจคำตอบ"}</button>}
      {feedback && <p role="status">{feedback.status === "queued" || feedback.status === "running" ? "กำลังตรวจคำตอบ…" : feedback.status === "succeeded" ? "ตรวจเสร็จแล้ว" : "ผลตรวจยังไม่พร้อม ต้องให้ผู้สอนตรวจเพิ่มเติม"}</p>}
      {feedback?.result?.items.map((item) => <p key={item.question_id}>
        <strong>{submission.questions.find((question) => question.id === item.question_id)?.ordinal}. {verdict[item.verdict]}</strong>
        {" — "}{item.explanation} {item.section_ids.join(", ")}
      </p>)}
      {error && <p role="alert">{error}</p>}
    </section>}
  </details>;
}
