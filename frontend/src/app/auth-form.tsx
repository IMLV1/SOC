"use client";
import Link from "next/link";
import GoogleLogin from "../features/google-login";
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
    event.preventDefault();
    setBusy(true);
    setMessage("");
    const form = event.currentTarget;
    const data = new FormData(form);
    const payload = {
      email: String(data.get("email")),
      password: String(data.get("password")),
      ...(register ? { display_name: String(data.get("display_name")) } : {}),
    };
    try {
      await mutate(register ? "/auth/register" : "/auth/login", payload);
      form.reset();
      if (register) {
        setDone(true);
        await refresh();
      } else {
        await refresh();
        router.push("/account");
      }
    } catch (error) {
      setMessage(
        error instanceof ApiError && error.status === 429
          ? "คำขอถี่เกินไป กรุณารอหนึ่งนาทีแล้วลองใหม่"
          : register
            ? "สมัครไม่สำเร็จ กรุณาตรวจข้อมูลหรือลองเข้าสู่ระบบ"
            : "เข้าสู่ระบบไม่สำเร็จ กรุณาตรวจข้อมูลและลองใหม่",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="auth-page">
      <aside className="auth-story" aria-label="เกี่ยวกับ Sentinel">
        <p className="eyebrow">SENTINEL / ANALYST WORKSPACE</p>
        <h2>
          เริ่มจากความสงสัย
          <br />
          <span>ไปให้ถึงหลักฐาน</span>
        </h2>
        <p>
          พื้นที่ฝึกของนักวิเคราะห์ ที่ทุกข้อสรุปมีเหตุผล
          และทุกเหตุการณ์คือโอกาสเรียนรู้
        </p>
        <ul className="auth-features">
          <li>
            <span aria-hidden="true">01</span>
            <div>
              <b>เรียนรู้ในระบบจำลอง</b>
              อ่านเหตุการณ์และสำรวจบริบทอย่างเป็นขั้นตอน
            </div>
          </li>
          <li>
            <span aria-hidden="true">02</span>
            <div>
              <b>เก็บกระบวนการคิดของคุณ</b>
              บันทึกการสืบสวนและอ้างอิงหลักฐานในที่เดียว
            </div>
          </li>
          <li>
            <span aria-hidden="true">03</span>
            <div>
              <b>กลับมาทำต่อได้</b>ประวัติการฝึกผูกกับบัญชีของคุณ
            </div>
          </li>
        </ul>
      </aside>
      <section className="auth-card" aria-labelledby="auth-title">
        <p className="eyebrow">
          {register ? "CREATE YOUR WORKSPACE" : "WELCOME BACK"}
        </p>
        <h1 id="auth-title">{register ? "สมัครสมาชิก" : "เข้าสู่ระบบ"}</h1>
        <p className="auth-description">
          {register
            ? "สร้างบัญชี Analyst เพื่อเริ่มเส้นทางการฝึกของคุณ"
            : "กลับมาสำรวจหลักฐาน และต่อยอดการสืบสวนของคุณ"}
        </p>
        {done ? (
          <div role="status" className="auth-success">
            <p>สมัครสำเร็จ กรุณาเข้าสู่ระบบด้วยบัญชีของคุณ</p>
            <Link className="button" href="/login">
              ไปเข้าสู่ระบบ
            </Link>
          </div>
        ) : (
          <form onSubmit={submit}>
            {register && (
              <label>
                ชื่อที่แสดง
                <input
                  name="display_name"
                  autoComplete="nickname"
                  required
                  maxLength={60}
                  placeholder="ชื่อที่ใช้ในพื้นที่ฝึก"
                />
              </label>
            )}
            <label>
              อีเมล
              <input
                name="email"
                type="email"
                autoComplete="username"
                required
                maxLength={254}
                placeholder="you@example.com"
              />
            </label>
            <label>
              รหัสผ่าน
              <input
                name="password"
                type="password"
                autoComplete={register ? "new-password" : "current-password"}
                required
                minLength={12}
                maxLength={128}
                placeholder="กรอกรหัสผ่านของคุณ"
                aria-describedby="password-help"
              />
            </label>
            <p className="form-help" id="password-help">
              รหัสผ่าน 12–128 ตัวอักษร
            </p>
            <button disabled={busy} type="submit">
              {busy
                ? "กำลังดำเนินการ…"
                : register
                  ? "สร้างบัญชี Analyst"
                  : "เข้าสู่ระบบ"}
            </button>
            {message && <p role="alert">{message}</p>}
          </form>
        )}
        {!register && (
          <>
            <div className="auth-divider">หรือเชื่อมต่อด้วย</div>
            <GoogleLogin />
          </>
        )}
        <p className="auth-links">
          {register ? "มีบัญชีอยู่แล้ว? " : "ยังไม่มีบัญชี? "}
          <Link href={register ? "/login" : "/register"}>
            {register ? "มีบัญชีแล้ว" : "สมัครบัญชีใหม่"}
          </Link>
          <Link className="demo-link" href="/demo">
            ดูตัวอย่างโดยไม่สมัคร <span aria-hidden="true">↗</span>
          </Link>
        </p>
      </section>
    </main>
  );
}
