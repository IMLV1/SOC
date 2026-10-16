"use client";
import Link from "next/link";
import { useSession } from "./session-provider";

export default function Home() {
  const { session, preview } = useSession();
  return (
    <main className="home-page">
      <div className="home-topline">
        <span className="brand">SOC LEARNING LAB / SENTINEL</span>
        <span className="badge">พื้นที่ฝึกจากข้อมูลจำลอง</span>
      </div>
      <section className="hero-grid" aria-labelledby="title">
        <div>
          <p className="eyebrow">THINK LIKE AN ANALYST</p>
          <h1 id="title">
            ทุกเหตุการณ์
            <br />
            มีเรื่องให้<em>ค้นหา</em>
          </h1>
          <p className="lead">
            ฝึกอ่านหลักฐาน เชื่อมเหตุการณ์ และอธิบายข้อสรุปอย่างมีเหตุผล
            ในพื้นที่จำลองสำหรับนักวิเคราะห์ความปลอดภัย
          </p>
          <div className="hero-actions">
            <Link
              className="button"
              href={preview ? "/demo" : session ? "/runs" : "/register"}
            >
              {preview
                ? "สำรวจตัวอย่าง"
                : session
                  ? "ไปหน้ารอบฝึก"
                  : "เริ่มต้นการฝึก"}
              <span aria-hidden="true">↗</span>
            </Link>
            <Link className="button button-secondary" href="/scenarios">
              ดูสถานการณ์ฝึก
            </Link>
          </div>
          <p className="hero-caption">
            {preview
              ? "Free preview · สมัครและดูตัวอย่างได้ ยังไม่มี runner ต่อเนื่อง"
              : "เรียนรู้ผ่านรอบฝึก หลักฐานจริงจากระบบจำลอง และบันทึกการสืบสวนของคุณ"}
          </p>
        </div>
        <div className="workflow-visual" aria-label="ขั้นตอนการฝึกวิเคราะห์">
          <div className="visual-topline">
            <span>THE INVESTIGATION WORKFLOW</span>
            <span>01 — 03</span>
          </div>
          <div className="visual-orbit" aria-hidden="true">
            <span className="orbit-node">&lt;/&gt;</span>
            <span className="orbit-line" />
            <span className="orbit-node">S</span>
            <span className="orbit-line" />
            <span className="orbit-node">✓</span>
          </div>
          <div className="workflow-step">
            <span className="step-index">01</span>
            <div>
              <b>สังเกตหลักฐาน</b>
              <small>Request · Response · Event logs</small>
            </div>
            <span className="step-symbol" aria-hidden="true">
              ↗
            </span>
          </div>
          <div className="workflow-step">
            <span className="step-index">02</span>
            <div>
              <b>เชื่อมโยงบริบท</b>
              <small>บัญชี เวลา และเหตุการณ์ต่อเนื่อง</small>
            </div>
            <span className="step-symbol" aria-hidden="true">
              ↗
            </span>
          </div>
          <div className="workflow-step">
            <span className="step-index">03</span>
            <div>
              <b>อธิบายสิ่งที่พบ</b>
              <small>ข้อสรุปที่ตรวจสอบย้อนกลับได้</small>
            </div>
            <span className="step-symbol" aria-hidden="true">
              ↗
            </span>
          </div>
        </div>
      </section>
      <section aria-labelledby="practice-heading">
        <div className="section-heading">
          <h2 id="practice-heading">ฝึกกระบวนการคิด ทีละหลักฐาน</h2>
          <p>จากการสังเกต สู่ข้อสรุปที่อธิบายได้</p>
        </div>
        <div className="levels">
          <article>
            <span>01 / OBSERVE</span>
            <h3>อ่านให้เข้าใจก่อนสรุป</h3>
            <p>
              แยกความพยายามออกจากผลกระทบ ด้วยรายละเอียดของ request และ response
            </p>
          </article>
          <article>
            <span>02 / INVESTIGATE</span>
            <h3>ต่อเหตุการณ์ให้เป็นเรื่อง</h3>
            <p>สำรวจหลักฐาน จัดการ ticket และบันทึกเหตุผลระหว่างการสืบสวน</p>
          </article>
          <article>
            <span>03 / EXPLAIN</span>
            <h3>สรุปพร้อมหลักฐานอ้างอิง</h3>
            <p>ระบุสิ่งที่พิสูจน์ได้ ข้อสันนิษฐาน และคำถามที่ต้องตรวจสอบต่อ</p>
          </article>
        </div>
      </section>
      <footer className="site-footer">
        <span>Sentinel / ฝึกวิเคราะห์อย่างมีเหตุผล</span>
        <span>ข้อมูลจำลองสำหรับการเรียนรู้ · ยังไม่เปิดให้สอบจริง</span>
      </footer>
    </main>
  );
}
