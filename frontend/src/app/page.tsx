"use client";

import Link from "next/link";
import { AuroraText } from "../components/magic-ui/aurora-text";
import { GridPattern } from "../components/magic-ui/grid-pattern";
import { MagicCard } from "../components/magic-ui/magic-card";
import { ShimmerLink } from "../components/magic-ui/shimmer-link";
import { useSession } from "./session-provider";

const workflow = [
  // Static learning sequence; this is orientation copy, not live run state.
  {
    number: "01",
    title: "สังเกตสิ่งที่เกิดขึ้น",
    detail: "อ่าน method, path, response และเวลา",
    code: "EVENT / OBSERVE",
  },
  {
    number: "02",
    title: "เชื่อมโยงหลักฐาน",
    detail: "เทียบบัญชี, source IP และ timeline",
    code: "CONTEXT / TRACE",
  },
  {
    number: "03",
    title: "อธิบายข้อสรุป",
    detail: "แยกสิ่งที่ยืนยันได้จากสิ่งที่ยังสงสัย",
    code: "REASON / REPORT",
  },
];

const learningPillars = [
  // Keep the three principles data-driven so labels, icons, and copy stay aligned.
  {
    index: "A",
    label: "หลักฐานมาก่อน",
    title: "เปิดดูรายละเอียดได้ทุกชิ้น",
    description:
      "ตรวจ request, response และ event ตามลำดับเวลา พร้อมอ้างอิงข้อมูลที่ใช้ประกอบข้อสรุป",
    icon: "⌕",
  },
  {
    index: "B",
    label: "ฝึกในพื้นที่จำลอง",
    title: "ทำงานกับข้อมูลที่ปลอดภัย",
    description:
      "สถานการณ์ทั้งหมดเป็นข้อมูลฝึก ไม่เชื่อมต่อระบบองค์กรหรือเครื่องมือป้องกันจริง",
    icon: "◈",
  },
  {
    index: "C",
    label: "เรียนต่อได้ภายหลัง",
    title: "ความคืบหน้าผูกกับบัญชี",
    description:
      "ระบบบันทึกความคืบหน้าผ่าน API ฝั่ง server เพื่อให้กลับมาทำต่อได้หลัง refresh",
    icon: "↗",
  },
];

export default function Home() {
  const { session, preview } = useSession();
  // Keep the primary action aligned with the current access state; the public
  // preview is read-only, while authenticated learners can return to their runs.
  const startHref = preview ? "/demo" : session ? "/runs" : "/register";
  const startLabel = preview
    ? "สำรวจข้อมูลตัวอย่าง"
    : session
      ? "กลับไปหน้ารอบฝึก"
      : "สร้างบัญชีเพื่อเริ่มเรียน";

  return (
    <main className="home-page">
      <section className="hero-stage" aria-labelledby="home-title">
        {/* These layers are visual texture only; the content below carries the meaning. */}
        <GridPattern className="hero-grid-pattern" />
        <div className="hero-stage__glow hero-stage__glow--left" />
        <div className="hero-stage__glow hero-stage__glow--right" />

        <div className="home-topline">
          <span className="home-topline__label">LEARNING SPACE / FIELD NOTES</span>
          <span className="safe-mode-pill">
            <span className="safe-mode-pill__dot" aria-hidden="true" />
            พื้นที่ฝึกจากข้อมูลจำลอง
          </span>
        </div>

        <div className="hero-grid">
          <div className="hero-copy">
            <p className="eyebrow hero-eyebrow">
              <span className="eyebrow__signal" aria-hidden="true" />
              SECURITY OPERATIONS / LEARNING TRACK
            </p>
            <h1 id="home-title">
              เห็นหลักฐาน
              <br />
              <AuroraText>คิดเป็นระบบ</AuroraText>
            </h1>
            <p className="lead hero-lead">
              ฝึกวิธีอ่านเหตุการณ์ เชื่อมโยงบริบท และอธิบายข้อสรุป
              ผ่านห้องทดลอง SOC ที่ออกแบบมาสำหรับการเรียนรู้ทีละขั้น
            </p>

            <div className="hero-actions">
              <ShimmerLink href={startHref}>
                {startLabel}
                <span aria-hidden="true">↗</span>
              </ShimmerLink>
              <Link className="button button-secondary" href="/scenarios">
                ดูสถานการณ์ฝึก
                <span aria-hidden="true">→</span>
              </Link>
            </div>

            <div className="hero-proof-row" aria-label="ขอบเขตของพื้นที่ฝึก">
              <span className="hero-proof-row__icon" aria-hidden="true">
                ◉
              </span>
              <p>
                ข้อมูลสังเคราะห์ · อ่านย้อนหลังได้ ·
                <strong>ไม่สั่งการระบบจริง</strong>
              </p>
            </div>
          </div>

          <MagicCard className="workflow-visual" aria-label="ขั้นตอนการฝึกวิเคราะห์">
            <div className="workflow-visual__header">
              <div>
                <span className="micro-label">WORKFLOW / 03 PHASES</span>
                <p>จากสัญญาณ สู่คำอธิบาย</p>
              </div>
              <span className="workflow-visual__status">
                <i aria-hidden="true" /> TRAINING MODE
              </span>
            </div>

            <div className="workflow-visual__telemetry" aria-hidden="true">
              {/* Decorative telemetry stays out of the accessibility tree. */}
              <span className="telemetry-ring telemetry-ring--outer" />
              <span className="telemetry-ring telemetry-ring--inner" />
              <span className="telemetry-core">SOC</span>
              <span className="telemetry-point telemetry-point--one" />
              <span className="telemetry-point telemetry-point--two" />
              <span className="telemetry-point telemetry-point--three" />
              <span className="telemetry-line telemetry-line--one" />
              <span className="telemetry-line telemetry-line--two" />
              <span className="telemetry-line telemetry-line--three" />
              <span className="telemetry-caption telemetry-caption--one">
                SIGNAL
              </span>
              <span className="telemetry-caption telemetry-caption--two">
                CONTEXT
              </span>
            </div>

            <ol className="workflow-list">
              {workflow.map((step) => (
                <li className="workflow-step" key={step.number}>
                  <span className="step-index">{step.number}</span>
                  <span className="workflow-step__body">
                    <strong>{step.title}</strong>
                    <small>{step.detail}</small>
                  </span>
                  <span className="workflow-step__code">{step.code}</span>
                </li>
              ))}
            </ol>
            <div className="workflow-visual__footer">
              <span>SIMULATION ENVIRONMENT</span>
              <span>READ ONLY / SAFE BY DESIGN</span>
            </div>
          </MagicCard>
        </div>
      </section>

      <section className="learning-section" aria-labelledby="learning-title">
        {/* The cards describe product principles, not promises of live integrations. */}
        <div className="section-heading">
          <div>
            <p className="eyebrow">THE ANALYST MINDSET</p>
            <h2 id="learning-title">ฝึกจากวิธีคิดที่ใช้ได้จริง</h2>
          </div>
          <p>
            ทุกส่วนเริ่มจากข้อเท็จจริงที่ตรวจสอบได้
            แล้วค่อยต่อยอดไปสู่คำอธิบาย
          </p>
        </div>

        <div className="learning-pillar-grid">
          {learningPillars.map((pillar) => (
            <article className="learning-pillar" key={pillar.index}>
              <div className="learning-pillar__topline">
                <span className="learning-pillar__index">{pillar.index}</span>
                <span className="learning-pillar__icon" aria-hidden="true">
                  {pillar.icon}
                </span>
              </div>
              <p className="learning-pillar__label">{pillar.label}</p>
              <h3>{pillar.title}</h3>
              <p className="learning-pillar__description">
                {pillar.description}
              </p>
            </article>
          ))}
        </div>
      </section>

      <section className="path-section" aria-labelledby="path-title">
        {/* This stage list orients learners; actual completion remains server-owned. */}
        <div className="path-section__copy">
          <p className="eyebrow">LEARN AT YOUR PACE</p>
          <h2 id="path-title">ค่อย ๆ เรียนรู้ ก่อนลงมือสืบสวน</h2>
          <p>
            เริ่มจากพื้นฐานการอ่าน request และ response
            จากนั้นฝึกดูความเชื่อมโยงของเหตุการณ์
            และเขียนเหตุผลให้คนอื่นตรวจสอบตามได้
          </p>
          <Link className="text-link" href="/learning">
            ดูเส้นทางการเรียนรู้ <span aria-hidden="true">→</span>
          </Link>
        </div>
        <div className="path-stages" aria-label="ระดับการเรียนรู้">
          <div className="path-stage path-stage--active">
            <span className="path-stage__node">01</span>
            <span>
              <strong>เริ่มต้น</strong>
              <small>อ่าน HTTP และหลักฐานเบื้องต้น</small>
            </span>
            <span className="path-stage__state">เส้นทางเรียนรู้</span>
          </div>
          <div className="path-stage">
            <span className="path-stage__node">02</span>
            <span>
              <strong>ระดับกลาง</strong>
              <small>เชื่อมเหตุการณ์และบริบท</small>
            </span>
            <span className="path-stage__state">ตามลำดับ</span>
          </div>
          <div className="path-stage">
            <span className="path-stage__node">03</span>
            <span>
              <strong>ชำนาญ</strong>
              <small>เทียบ baseline และอธิบาย anomaly</small>
            </span>
            <span className="path-stage__state">ตามลำดับ</span>
          </div>
        </div>
      </section>

      <section className="home-bottom-cta" aria-labelledby="start-learning-title">
        {/* Repeat the state-aware primary action at the end of the long landing page. */}
        <GridPattern className="home-bottom-cta__pattern" />
        <div>
          <p className="eyebrow">YOUR NEXT INVESTIGATION STARTS HERE</p>
          <h2 id="start-learning-title">พร้อมเปิดดูหลักฐานชิ้นแรกหรือยัง</h2>
          <p>เริ่มจากบทเรียนหรือสำรวจตัวอย่างได้ตามจังหวะของคุณ</p>
        </div>
        <div className="home-bottom-cta__actions">
          <ShimmerLink href={startHref}>{startLabel}</ShimmerLink>
          <Link className="button button-quiet" href="/demo">
            เปิดข้อมูลตัวอย่าง
          </Link>
        </div>
      </section>

      <footer className="site-footer">
        <div className="brand-lockup brand-lockup--footer">
          <span className="brand-lockup__symbol" aria-hidden="true">
            S
          </span>
          <span className="brand-lockup__name">
            SENTINEL
            <small>SOC LEARNING LAB</small>
          </span>
        </div>
        <p>ห้องทดลองสำหรับการเรียนรู้ · ข้อมูลจำลองเท่านั้น</p>
        <Link href="/scenarios">สำรวจสถานการณ์ฝึก</Link>
      </footer>
    </main>
  );
}
