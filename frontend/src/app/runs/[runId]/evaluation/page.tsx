"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, read } from "../../../../lib/api";
import { useSession } from "../../../session-provider";

type Evaluation = {
  id: string;
  run_id: string;
  revision: number;
  status: "completed";
  release_cutoff: number;
  assessment_cutoff: string;
  dataset_hash: string;
  truncated: boolean;
  metrics: Record<string, number | null | string>;
  versions: Record<string, unknown>;
};

export default function EvaluationPage() {
  const { runId } = useParams<{ runId: string }>();
  const { session, loading: sessionLoading } = useSession();
  const [result, setResult] = useState<Evaluation | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!session || !runId) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    let delay = 1000;
    async function poll() {
      try {
        const data = await read<Evaluation>(`/runs/${runId}/evaluation`);
        if (!active) return;
        setResult(data);
        setError("");
      } catch (cause) {
        if (!active) return;
        if (
          cause instanceof ApiError &&
          cause.status === 409 &&
          cause.code === "EVALUATION_PENDING"
        ) {
          setError("กำลังรอ pipeline drain และตรึงผลประเมิน");
          timer = setTimeout(poll, delay);
          delay = Math.min(delay * 2, 10000);
          return;
        }
        setError(
          cause instanceof ApiError && cause.status === 401
            ? "เซสชันหมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง"
            : "โหลดผลประเมินไม่สำเร็จ",
        );
      }
    }
    void poll();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [session, runId]);
  return (
    <main className="run-shell">
      <div className="run-topline">
        <Link href={`/runs/${runId}`}>กลับไปยังรอบฝึก</Link>
        <span>Evaluation</span>
      </div>
      <h1>ผลประเมินรอบฝึก</h1>
      {sessionLoading ? (
        <p role="status">กำลังตรวจบัญชี…</p>
      ) : !session ? (
        <p>
          <Link href="/login">เข้าสู่ระบบเพื่อดูผล</Link>
        </p>
      ) : null}
      {!result ? (
        <p role="status">{error || "กำลังโหลดผลประเมิน…"}</p>
      ) : (
        <>
          {result.truncated && (
            <p role="status">
              รอบนี้จบก่อนปล่อยเหตุการณ์ทั้งหมด; ตัวชี้วัดระบุ incomplete groups
            </p>
          )}
          <p>
            Snapshot SHA-256: <code>{result.dataset_hash}</code>
          </p>
          <p>
            Release cutoff: {result.release_cutoff} · ปิดรับ assessment:{" "}
            {new Date(result.assessment_cutoff).toLocaleString("th-TH")}
          </p>
          <p>
            หน่วยวัด: {String(result.metrics.unit)} · TP{" "}
            {String(result.metrics.tp)} · FP {String(result.metrics.fp)} · FN{" "}
            {String(result.metrics.fn)} · TN {String(result.metrics.tn)}
          </p>
          <p>
            Precision:{" "}
            {result.metrics.precision == null
              ? `N/A (${String(result.metrics.precision_null_reason)})`
              : String(result.metrics.precision)}{" "}
            · Recall:{" "}
            {result.metrics.recall == null
              ? `N/A (${String(result.metrics.recall_null_reason)})`
              : String(result.metrics.recall)}
          </p>
          <p>
            Incomplete groups: {String(result.metrics.incomplete_groups)} ·
            Undetermined: {String(result.metrics.undetermined_groups)}
          </p>
          <a href={`/api/v1/runs/${runId}/export`}>ดาวน์โหลด JSON snapshot</a>
        </>
      )}
    </main>
  );
}
