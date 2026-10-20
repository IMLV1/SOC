"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, read } from "../../../lib/api";
import { useSession } from "../../session-provider";

type ExamItem = { id: string; owner_user_id: string; display_name: string; level_id: string; status: string; version: number; submitted_at: string | null };

export default function InstructorExamsPage() {
  const { session, loading } = useSession();
  const [items, setItems] = useState<ExamItem[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!session || session.user.role !== "instructor") return;
    read<ExamItem[]>("/admin/exam-attempts").then(setItems).catch((cause) => setError(cause instanceof ApiError && cause.status === 401 ? "เซสชันหมดอายุ" : "โหลดรายการข้อสอบไม่สำเร็จ"));
  }, [session]);
  return <main className="run-shell"><p><Link href="/instructor">← Instructor</Link></p><h1>ตรวจข้อสอบ</h1>
    {loading ? <p role="status">กำลังตรวจบัญชี…</p> : !session ? <p><Link href="/login">เข้าสู่ระบบ</Link></p> : session.user.role !== "instructor" ? <p role="alert">หน้านี้ใช้ได้เฉพาะ Instructor</p> : error ? <p role="alert">{error}</p> : items.length === 0 ? <p>ไม่มีข้อสอบในขอบเขตที่ได้รับมอบหมาย</p> : <ol className="run-list">{items.map((item) => <li key={item.id}><Link href={`/instructor/exams/${item.id}`}>{item.display_name} · {item.status}</Link><small>{item.submitted_at ? ` · ${new Date(item.submitted_at).toLocaleString("th-TH")}` : ""}</small></li>)}</ol>}
  </main>;
}
