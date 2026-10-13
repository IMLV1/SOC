"use client";
import Link from "next/link";
import { useSession } from "../session-provider";
export default function Account() {
  const { session, loading, error } = useSession();
  if (loading) return <main role="status">กำลังตรวจบัญชี…</main>;
  if (!session) return <main><h1>กรุณาเข้าสู่ระบบ</h1><p>{error || "ไม่มี session ที่ใช้งานได้ หรือ session หมดอายุแล้ว"}</p><Link href="/login">เข้าสู่ระบบ</Link></main>;
  return <main><h1>บัญชีของคุณ</h1><dl>
    <dt>ชื่อ</dt><dd>{session.user.display_name}</dd><dt>อีเมล</dt><dd>{session.user.email}</dd>
    <dt>บทบาท</dt><dd>{session.user.role === "instructor" ? "Instructor" : "Analyst"}</dd>
  </dl><p>เข้าสู่ระบบแล้ว รอบฝึก บทเรียน และข้อสอบจะเพิ่มในขั้นถัดไป</p><Link href="/demo">อ่านข้อมูลตัวอย่าง</Link></main>;
}
