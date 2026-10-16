"use client";
import Link from "next/link";
import GoogleLogin from "../../features/google-login";
import { useSession } from "../session-provider";
export default function Account() {
  const { session, loading, error, preview } = useSession();
  if (loading) return <main role="status">กำลังตรวจบัญชี…</main>;
  if (!session)
    return (
      <main>
        <h1>กรุณาเข้าสู่ระบบ</h1>
        <p>{error || "ไม่มี session ที่ใช้งานได้ หรือ session หมดอายุแล้ว"}</p>
        <Link href="/login">เข้าสู่ระบบ</Link>
      </main>
    );
  return (
    <main className="account-page">
      <p className="eyebrow">YOUR ANALYST WORKSPACE</p>
      <h1>บัญชีของคุณ</h1>
      <p>จัดการการเข้าสู่ระบบ และกลับไปต่อยอดการฝึกของคุณ</p>
      <div className="account-grid">
        <section className="account-card" aria-labelledby="profile-title">
          <div className="profile-avatar" aria-hidden="true">
            {session.user.display_name.slice(0, 1).toUpperCase()}
          </div>
          <h2 id="profile-title">ข้อมูลบัญชี</h2>
          <dl className="profile-details">
            <div>
              <dt>ชื่อ</dt>
              <dd>{session.user.display_name}</dd>
            </div>
            <div>
              <dt>อีเมล</dt>
              <dd>{session.user.email}</dd>
            </div>
            <div>
              <dt>บทบาท</dt>
              <dd>
                <span className="badge">
                  {session.user.role === "instructor"
                    ? "Instructor"
                    : "Analyst"}
                </span>
              </dd>
            </div>
          </dl>
          <div className="hero-actions">
            <Link className="button" href="/runs">
              ไปหน้ารอบฝึก <span aria-hidden="true">↗</span>
            </Link>
            <Link className="button button-secondary" href="/demo">
              อ่านข้อมูลตัวอย่าง
            </Link>
          </div>
        </section>
        <section className="account-card" aria-labelledby="connection-title">
          <p className="eyebrow">CONNECTED ACCOUNT</p>
          <h2 id="connection-title">การเชื่อมต่อ Google</h2>
          <GoogleLogin account />
        </section>
      </div>
      <p className="notice">
        {preview
          ? "Free preview: สมัคร เข้าสู่ระบบ และดูตัวอย่างได้ ยังไม่มี runner สำหรับเริ่มรอบฝึก"
          : "รอบฝึก S02 เปิดใช้งานแล้ว ส่วนบทเรียนแบบลำดับขั้นและข้อสอบยังไม่เปิด"}
      </p>
    </main>
  );
}
