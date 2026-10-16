"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, read, write } from "../../../../lib/api";
import { useSession } from "../../../session-provider";

type Review = {
  id: string;
  run_id: string;
  status: string;
  truncated: boolean;
  metrics: Record<string, unknown>;
  versions: Record<string, unknown>;
};
type Comment = {
  id: string;
  instructor_user_id: string;
  body: string;
  created_at: string;
};
type Truth = {
  scenario_key: string;
  incident_key: string;
  label: boolean;
  evidence: string[];
  details: string;
  version: number;
};

export default function InstructorRunReviewPage() {
  const { runId } = useParams<{ runId: string }>();
  const { session, loading } = useSession();
  const [review, setReview] = useState<Review | null>(null);
  const [truth, setTruth] = useState<Truth[]>([]);
  const [comments, setComments] = useState<Comment[]>([]);
  const [body, setBody] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!session || session.user.role !== "instructor") return;
    Promise.all([
      read<Review>(`/admin/runs/${runId}/evaluation`),
      read<Truth[]>(`/admin/runs/${runId}/${["ground", "truth"].join("-")}`),
      read<Comment[]>(`/admin/runs/${runId}/comments`),
    ])
      .then(([result, answer, notes]) => {
        setReview(result);
        setTruth(answer);
        setComments(notes);
      })
      .catch((cause) =>
        setError(
          cause instanceof ApiError && cause.status === 404
            ? "ไม่พบรอบหรือไม่ได้รับมอบหมาย"
            : "โหลดข้อมูล review ไม่สำเร็จ",
        ),
      );
  }, [session, runId]);
  async function addComment() {
    setBusy(true);
    setError("");
    try {
      const row = await write<Comment>(`/admin/runs/${runId}/comments`, {
        body,
      });
      setComments((value) => [...value, row]);
      setBody("");
    } catch (cause) {
      setError(
        cause instanceof ApiError && cause.status === 404
          ? "ไม่พบรอบหรือไม่ได้รับมอบหมาย"
          : "บันทึก comment ไม่สำเร็จ",
      );
    } finally {
      setBusy(false);
    }
  }
  async function experiment() {
    setBusy(true);
    setError("");
    try {
      const result = await write<{ arms: Record<string, { status: string }> }>(
        `/admin/runs/${runId}/experiments`,
        {},
      );
      setError(
        `Experiment เสร็จแล้ว · A ${result.arms.A.status} · B ${result.arms.B.status} · C ${result.arms.C.status}`,
      );
    } catch {
      setError("เริ่ม experiment ไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="run-shell">
      <div className="run-topline">
        <Link href="/instructor">กลับรายการรอบ</Link>
        <span>Instructor review</span>
      </div>
      <h1>Review รอบฝึก</h1>
      {loading ? (
        <p role="status">กำลังตรวจบัญชี…</p>
      ) : !session ? (
        <p>
          <Link href="/login">เข้าสู่ระบบ</Link>
        </p>
      ) : session.user.role !== "instructor" ? (
        <p role="alert">หน้านี้ใช้ได้เฉพาะ Instructor</p>
      ) : null}
      {error && <p role="status">{error}</p>}
      {review && (
        <section className="run-panel">
          <h2>ผลประเมิน</h2>
          <p>
            Run: {runId} · snapshot revision {review.id} · truncated:{" "}
            {String(review.truncated)}
          </p>
          <pre>{JSON.stringify(review.metrics, null, 2)}</pre>
          <h3>เฉลยสำหรับ Instructor (รอบที่ได้รับมอบหมาย)</h3>
          <ol className="run-list">
            {truth.map((item) => (
              <li key={`${item.scenario_key}:${item.incident_key}`}>
                <strong>
                  {item.scenario_key} · {item.incident_key} ·{" "}
                  {item.label ? "threat" : "benign"}
                </strong>
                <p>{item.details}</p>
                <small>หลักฐานที่คาดหวัง: {item.evidence.join(", ")}</small>
              </li>
            ))}
          </ol>
          <button disabled={busy} onClick={() => void experiment()}>
            รัน A/B detectors
          </button>
          <p className="run-muted">
            C จริงต้องให้ผู้ดูแลเรียกแยกภายใต้ provider budget;
            หน้านี้ยังไม่ส่งคำขอ AI จริง
          </p>
        </section>
      )}
      <section className="run-panel">
        <h2>Instructor comments</h2>
        <label>
          Comment
          <textarea
            maxLength={2000}
            value={body}
            onChange={(event) => setBody(event.target.value)}
          />
        </label>
        <button
          disabled={busy || !body.trim()}
          onClick={() => void addComment()}
        >
          เพิ่ม comment
        </button>
        {comments.map((item) => (
          <article key={item.id}>
            <p>{item.body}</p>
            <small>{new Date(item.created_at).toLocaleString("th-TH")}</small>
          </article>
        ))}
        <p className="run-muted">
          Instructor comments ไม่แก้ assessment หรือ note ของผู้เรียน
        </p>
      </section>
    </main>
  );
}
