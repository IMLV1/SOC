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
      <p>เริ่มจากบทเรียนพื้นฐานก่อนทำข้อสอบเลื่อนระดับ หรือเปิดรอบฝึกแยกต่างหากเพื่อสำรวจเคส</p>
      <section className="account-next" aria-labelledby="account-next-title">
        <p className="eyebrow">เริ่มตรงนี้</p>
        <h2 id="account-next-title">เส้นทางสำหรับผู้เริ่มต้น</h2>
        <ol>
          <li>ลองกดอ่าน request ตัวอย่าง (ไม่บันทึกคะแนน)</li>
          <li>เรียนบทพื้นฐานทีละขั้น ระบบบันทึกความคืบหน้า</li>
          <li>จบบทเรียนแล้วจึงเริ่มข้อสอบระดับเริ่มต้น</li>
        </ol>
        <div className="hero-actions">
          <Link className="button" href={preview ? "/demo" : "/learning"}>{preview ? "ลองข้อมูลตัวอย่าง" : "เริ่มบทเรียนพื้นฐาน"}</Link>
          <Link className="button button-secondary" href="/demo">ดูตัวอย่างก่อน</Link>
        </div>
      </section>
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
            {!preview && <Link className="button button-secondary" href="/runs">เปิดรอบฝึก (แยกจากข้อสอบ)</Link>}
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
          : "บทเรียนและข้อสอบระดับเริ่มต้นเปิดแล้ว; ผู้ช่วยสอนใช้ Dify เมื่อ release พร้อม และข้อเขียนขอ feedback ได้หลังส่งคำตอบ ส่วน AI วิเคราะห์รอบฝึกยังเป็น mock"}
      </p>
    </main>
  );
}
