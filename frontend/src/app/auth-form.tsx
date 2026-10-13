"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, mutate } from "../lib/api";
import { useSession } from "./session-provider";

export default function AuthForm({ register = false }: { register?: boolean }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [done, setDone] = useState(false);
  const router = useRouter();
  const { refresh } = useSession();
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setMessage("");
    const form = event.currentTarget;
    const data = new FormData(form);
    const payload = { email: String(data.get("email")), password: String(data.get("password")),
      ...(register ? { display_name: String(data.get("display_name")) } : {}) };
    try {
      await mutate(register ? "/auth/register" : "/auth/login", payload);
      form.reset();
      if (register) { setDone(true); await refresh(); }
      else { await refresh(); router.push("/account"); }
    } catch (error) {
      setMessage(error instanceof ApiError && error.status === 429 ? "คำขอถี่เกินไป กรุณารอหนึ่งนาทีแล้วลองใหม่" :
        register ? "สมัครไม่สำเร็จ กรุณาตรวจข้อมูลหรือลองเข้าสู่ระบบ" : "เข้าสู่ระบบไม่สำเร็จ กรุณาตรวจข้อมูลและลองใหม่");
    } finally { setBusy(false); }
  }
  return <main className="auth-page"><h1>{register ? "สมัครสมาชิก" : "เข้าสู่ระบบ"}</h1>
    {done ? <div role="status"><p>สมัครสำเร็จ กรุณาเข้าสู่ระบบด้วยบัญชีของคุณ</p><Link href="/login">ไปเข้าสู่ระบบ</Link></div> :
    <form onSubmit={submit}>
      {register && <label>ชื่อที่แสดง<input name="display_name" autoComplete="nickname" required maxLength={60} /></label>}
      <label>อีเมล<input name="email" type="email" autoComplete="username" required maxLength={254} /></label>
      <label>รหัสผ่าน<input name="password" type="password" autoComplete={register ? "new-password" : "current-password"} required minLength={12} maxLength={128} /></label>
      <p>รหัสผ่าน 12–128 ตัวอักษร</p>
      <button disabled={busy} type="submit">{busy ? "กำลังดำเนินการ…" : register ? "สร้างบัญชี Analyst" : "เข้าสู่ระบบ"}</button>
      {message && <p role="alert">{message}</p>}
    </form>}
    <p><Link href={register ? "/login" : "/register"}>{register ? "มีบัญชีแล้ว" : "สมัครบัญชีใหม่"}</Link> · <Link href="/demo">ดูตัวอย่างโดยไม่สมัคร</Link></p>
  </main>;
}
