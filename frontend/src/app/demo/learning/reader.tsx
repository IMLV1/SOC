"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import curriculumData from "../../../../public/learning/curriculum-v1.json";
import { selectTrainingStep, trainingLink, type Curriculum } from "../../../lib/curriculum";
import PracticeWorkbench from "./workbench";

const curriculum: Curriculum = curriculumData;

function AiWorkflow() {
  return <section className="learning-card" aria-labelledby="ai-workflow-title">
    <h2 id="ai-workflow-title">ถาม AI ตอนไหน และ RAG ใช้ตรงไหน</h2>
    <p>ตอนนี้ยังไม่เรียก AI หรือ Dify จริง หน้านี้ใช้บทเรียนจาก JSON เท่านั้น</p>
    <ol className="lesson-steps">
      <li><strong>ตอนเรียน:</strong> ถามความหมาย เช่น “401 บอกอะไรได้บ้าง” RAG ค้นคู่มือที่อนุมัติ แล้ว AI อธิบายพร้อมแหล่งอ้างอิง ไม่ค้นเฉลยสอบ</li>
      <li><strong>ตอนฝึก:</strong> หลังลองวิเคราะห์เอง ถาม “หลักฐานนี้ยังขาดอะไร” ระบบจริงต้องส่งเฉพาะ evidence snapshot ของรอบที่มีสิทธิ์อ่าน พร้อมความรู้จาก RAG คำตอบ AI ไม่แก้ assessment ของคน</li>
      <li><strong>ระหว่างสอบ ก่อนส่ง:</strong> ไม่เปิด Ask AI ไม่แสดงคำใบ้หรือเฉลย ผู้เรียนต้องเลือกหลักฐานและสรุปเอง</li>
      <li><strong>หลังส่งข้อสอบ:</strong> freeze คำตอบก่อน จากนั้นจึงใช้กฎและ AI/RAG ช่วยตรวจเหตุผลตาม rubric ที่กำหนด หากกำกวมหรือระบบไม่พร้อมให้ needs_review และส่งคนตรวจ ไม่ auto-pass</li>
    </ol>
    <p><strong>RAG ไม่ใช่หลักฐานของเหตุการณ์:</strong> คู่มืออธิบายหลักการ ส่วน request/response/log ใช้ยืนยันสิ่งที่เกิดในเคส ต้องตรวจ citation ว่าสนับสนุนข้อความจริงและยังมีสิทธิ์ใช้</p>
    <button type="button" disabled aria-describedby="dify-unavailable">ถาม AI — ยังไม่เชื่อม Dify</button>
    <p id="dify-unavailable">ต้องกำหนด workflow, corpus ที่อนุมัติ, citations, usage/งบ และ secret ฝั่ง server ก่อน จึงเปิดใช้งานจริงได้ ไม่ใส่ key ใน JSON หรือ browser</p>
  </section>;
}

export default function CurriculumPreview() {
  const search = useSearchParams();
  const router = useRouter();
  const { level, lesson, step, stepIndex, lessons } = selectTrainingStep(curriculum, search.get("lesson"), search.get("step"));
  const view = search.get("view");
  const [revealed, setRevealed] = useState<string | null>(null);
  const [visited, setVisited] = useState<Set<string>>(new Set());
  const stepKey = `${lesson.id}/${step.id}`;
  const explanationVisible = revealed === stepKey;
  const lessonIndex = lessons.findIndex((item) => item.id === lesson.id);
  const stepTotal = lessons.reduce((total, item) => total + item.steps.length, 0);
  const nextLesson = lessons[lessonIndex + 1];

  function openStep(lessonId: string, stepId?: string) {
    setRevealed(null);
    router.push(trainingLink(lessonId, stepId), { scroll: false });
  }

  function revealStep() {
    setRevealed(stepKey);
    setVisited((current) => new Set(current).add(stepKey));
  }

  return <main className="account-page learning-page curriculum-preview">
    <p className="eyebrow">บทเรียนจากไฟล์ · Preview</p>
    <h1>เรียนรู้ SOC ทีละขั้น</h1>
    <p>3 ระดับ · {lessons.length} บทเรียน · {stepTotal} ขั้น จาก curriculum-v1.json</p>
    <p className="notice">โหมดทดลองเนื้อหา ไม่เรียก API/ฐานข้อมูล ไม่บันทึกคะแนนหรือปลดล็อกบัญชี ทุกระดับเปิดให้อ่านเพื่อทดสอบ ไม่ใช่การข้าม gate ของระบบจริง ร่างฝึกและจำนวนที่อ่านจะหายเมื่อรีเฟรช</p>
    <nav className="demo-actions" aria-label="ส่วนของบทเรียนตัวอย่าง">
      <Link className="button button-secondary" href={trainingLink(lesson.id, step.id)} aria-current={!view || !["practice", "ai"].includes(view) ? "page" : undefined}>อ่านบทเรียน</Link>
      <Link className="button button-secondary" href="/demo/learning?view=practice" aria-current={view === "practice" ? "page" : undefined}>ฝึกอ่านหลักฐานรวม</Link>
      <Link className="button button-secondary" href="/demo/learning?view=ai" aria-current={view === "ai" ? "page" : undefined}>AI / RAG ใช้ตอนไหน</Link>
    </nav>

    {view !== "practice" && view !== "ai" && <div>
      <label htmlFor="preview-lesson">เลือกบทเรียนจากไฟล์</label>
      <select id="preview-lesson" value={lesson.id} onChange={(event) => openStep(event.target.value)}>
        {curriculum.levels.map((item) => <optgroup key={item.id} label={`ระดับ ${item.ordinal}: ${item.title}`}>
          {item.lessons.map((entry) => <option key={entry.id} value={entry.id}>{entry.title}</option>)}
        </optgroup>)}
      </select>
    </div>}

    {view === "practice" ? <PracticeWorkbench curriculum={curriculum} /> : view === "ai" ? <AiWorkflow /> : <>
      <div className="curriculum-layout">
        <aside className="curriculum-catalog" aria-label="สารบัญบทเรียน">
          {curriculum.levels.map((item) => <section key={item.id} className="learning-card">
            <h2>ระดับ {item.ordinal}: {item.title}</h2>
            <p>{item.objective}</p>
            <ol className="curriculum-lessons">{item.lessons.map((entry) => <li key={entry.id}>
              <Link href={trainingLink(entry.id)} aria-current={entry.id === lesson.id ? "page" : undefined}>{entry.title}</Link>
            </li>)}</ol>
          </section>)}
        </aside>
        <div className="curriculum-reader">
          <section className="learning-card">
            <p className="eyebrow">ระดับ {level.ordinal}: {level.title} · บท {lessonIndex + 1} / {lessons.length}</p>
            <h2>{lesson.title}</h2>
            <p>ตัวอย่างฝึก ไม่ใช่ข้อสอบ · อ่านตัวอย่างแล้ว {visited.size} / {stepTotal} จุดในหน้านี้</p>
            <ol className="curriculum-steps" aria-label="ขั้นในบทเรียน">{lesson.steps.map((entry) => <li key={entry.id}>
              <Link href={trainingLink(lesson.id, entry.id)} aria-current={step.id === entry.id ? "step" : undefined}>{entry.title}</Link>
            </li>)}</ol>
          </section>
          <section key={stepKey} className="learning-card curriculum-active-step" aria-labelledby="current-step-title">
            <p className="eyebrow">ขั้น {stepIndex + 1} / {lesson.steps.length}</p>
            <h2 id="current-step-title">{step.title}</h2>
            <p>กดข้อมูลตัวอย่างเพื่อเปิดคำอธิบาย ก่อนขยับไปขั้นถัดไป</p>
            <button className="lesson-target" type="button" aria-expanded={explanationVisible} aria-controls="step-explanation" onClick={revealStep}>
              <span>กดดู: {step.title}</span><code>{step.target}</code>
            </button>
            <div id="step-explanation" hidden={!explanationVisible} className="lesson-explanation">
              <h3>ดูตรงไหน และหมายความว่าอะไร</h3><p>{step.explanation}</p>
              <h3>สิ่งที่ยังสรุปไม่ได้</h3><p>{step.limitation}</p>
            </div>
            <div className="demo-actions">
              <button className="button-secondary" type="button" disabled={stepIndex === 0 && lessonIndex === 0} onClick={() => {
                const previousLesson = lessons[lessonIndex - 1];
                if (stepIndex > 0) openStep(lesson.id, lesson.steps[stepIndex - 1].id);
                else if (previousLesson) openStep(previousLesson.id, previousLesson.steps.at(-1)?.id);
              }}>ย้อนกลับ</button>
              {stepIndex < lesson.steps.length - 1
                ? <button type="button" disabled={!explanationVisible} onClick={() => openStep(lesson.id, lesson.steps[stepIndex + 1].id)}>เข้าใจแล้ว ไปขั้นถัดไป</button>
                : nextLesson
                  ? <button type="button" disabled={!explanationVisible} onClick={() => openStep(nextLesson.id)}>ไปบทถัดไป: {nextLesson.title}</button>
                  : <button type="button" disabled={!explanationVisible} onClick={() => router.push("/demo/learning?view=practice")}>ลองฝึกอ่านหลักฐานรวม</button>}
            </div>
            {stepIndex === lesson.steps.length - 1 && <p>จบเนื้อหาบทนี้ไม่เท่ากับผ่านข้อสอบ ไม่มีการบันทึกผลผ่านจากหน้านี้</p>}
          </section>
          <section className="learning-card">
            <h2>จากบทเรียนไปสู่การทดสอบจริง</h2>
            <p>ลองฝึกอ่านหลักฐานโดยไม่มีคำชี้ทีละช่องได้ในโหมดฝึก แต่ยังไม่ให้คะแนน ส่วนการสอบจริงต้องตรวจ gate และเก็บคำตอบฝั่ง server ซึ่งไม่อยู่ในโหมด JSON นี้</p>
            <div className="demo-actions"><Link className="button button-secondary" href="/demo/learning?view=practice">ลองฝึกอ่านหลักฐานรวม</Link><Link href="/learning" prefetch={false}>ไปบทเรียนบัญชีจริง (ต้องใช้ backend)</Link></div>
          </section>
        </div>
      </div>
    </>}
  </main>;
}
