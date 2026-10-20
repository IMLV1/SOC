"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, read } from "../../lib/api";
import { useSession } from "../session-provider";

type AssignedRun = {
  id: string;
  owner_user_id: string;
  display_name: string;
  status: string;
  version: number;
  created_at: string;
  evaluated: boolean;
};

export default function InstructorRunsPage() {
  const { session, loading } = useSession();
  const [runs, setRuns] = useState<AssignedRun[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!session || session.user.role !== "instructor") return;
    read<AssignedRun[]>("/admin/runs")
      .then(setRuns)
      .catch((cause) => {
        setError(
          cause instanceof ApiError && cause.status === 401
            ? "เซสชันหมดอายุ"
            : "โหลดรอบที่ได้รับมอบหมายไม่สำเร็จ",
        );
      });
  }, [session]);
  return (
    <main className="run-shell">
      <h1>Instructor · รอบที่ได้รับมอบหมาย</h1>
      <p><Link href="/instructor/exams">ตรวจข้อสอบใน assignment ของคุณ</Link></p>
      {loading ? (
        <p role="status">กำลังตรวจบัญชี…</p>
      ) : !session ? (
        <p>
          <Link href="/login">เข้าสู่ระบบ</Link>
        </p>
      ) : session.user.role !== "instructor" ? (
        <p role="alert">หน้านี้ใช้ได้เฉพาะ Instructor</p>
      ) : error ? (
        <p role="alert">{error}</p>
      ) : runs.length === 0 ? (
        <p>ยังไม่มีรอบที่ได้รับมอบหมาย</p>
      ) : (
        <ol className="run-list">
          {runs.map((run) => (
            <li key={run.id}>
              <Link href={`/instructor/runs/${run.id}`}>
                {run.display_name} · {run.status} ·{" "}
                {run.evaluated ? "มีผลประเมิน" : "รอประเมิน"}
              </Link>
              <small>
                {" "}
                · {new Date(run.created_at).toLocaleString("th-TH")}
              </small>
            </li>
          ))}
        </ol>
      )}
    </main>
  );
}
