"use client";

import Link from "next/link";
import { useState } from "react";
import practice from "../../../../public/learning/practice-v1.json";
import { trainingLink, type Curriculum } from "../../../lib/curriculum";

type Draft = { evidence: string[]; severity: string; disposition: string; reason: string };
const emptyDraft: Draft = { evidence: [], severity: "", disposition: "", reason: "" };

export default function PracticeWorkbench({ curriculum }: { curriculum: Curriculum }) {
  const [filter, setFilter] = useState("all");
  const [caseId, setCaseId] = useState(practice.cases[0].id);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [checked, setChecked] = useState<string | null>(null);
  const [guide, setGuide] = useState<string | null>(null);
  const cases = practice.cases.filter((item) => filter === "all" || String(item.level) === filter);
  const currentCase = cases.find((item) => item.id === caseId) ?? cases[0];
  const draft = drafts[currentCase.id] ?? emptyDraft;
  const lessons = curriculum.levels.flatMap((level) => level.lessons).filter((lesson) => currentCase.lesson_ids.includes(lesson.id));
  const missing = [
    draft.evidence.length === 0 && "เลือก event ที่ใช้เป็นหลักฐาน",
    !draft.severity && "เลือก severity",
    !draft.disposition && "เลือก disposition",
    !draft.reason.trim() && "เขียนเหตุผลและสิ่งที่ยังไม่ทราบ",
  ].filter(Boolean);

  function updateDraft(update: Partial<Draft>) {
    setDrafts((previous) => ({ ...previous, [currentCase.id]: { ...draft, ...update } }));
    setChecked(null);
  }

  return <section className="learning-card" aria-labelledby="practice-title">
    <h2 id="practice-title">ฝึกอ่านหลักฐานรวม</h2>
    <p>ข้อมูลฝึกจาก practice-v1.json ทั้งหมดแสดงไว้แล้ว ไม่ใช่ runner หรือข้อสอบ ไม่กด URL หรือรันข้อความใน log ลองวิเคราะห์ก่อนเปิดคู่มือ ไม่มีคะแนนหรือการส่งคำตอบออกจาก browser</p>
    <label htmlFor="practice-level">เลือกกลุ่มตัวอย่าง</label>
    <select id="practice-level" value={filter} onChange={(event) => { setFilter(event.target.value); setChecked(null); setGuide(null); }}>
      <option value="all">ทุกระดับพร้อมกัน</option>
      {curriculum.levels.map((level) => <option key={level.id} value={level.ordinal}>ระดับ {level.ordinal}: {level.title}</option>)}
    </select>
    <div className="demo-event-picker" aria-label="เลือกเคสฝึก">{cases.map((item) => <button type="button" key={item.id} aria-pressed={item.id === currentCase.id} onClick={() => { setCaseId(item.id); setChecked(null); setGuide(null); }}>{item.title}</button>)}</div>
    <h3>{currentCase.title}</h3><p>{currentCase.prompt}</p>
    <ol className="curriculum-events">{currentCase.events.map((event) => <li key={event.id}>
      <label><input type="checkbox" checked={draft.evidence.includes(event.id)} onChange={(change) => updateDraft({ evidence: change.target.checked ? [...draft.evidence, event.id] : draft.evidence.filter((id) => id !== event.id) })} /> ใช้หลักฐาน {event.id} · {event.source}</label>
      <pre className="lesson-evidence"><code>{JSON.stringify(event, null, 2)}</code></pre>
    </li>)}</ol>
    <fieldset className="curriculum-draft"><legend>ร่างผลวิเคราะห์ของคุณ — เฉพาะหน้านี้</legend>
      <label htmlFor="practice-severity">Severity</label><select id="practice-severity" value={draft.severity} onChange={(event) => updateDraft({ severity: event.target.value })}>
        <option value="">เลือกความรุนแรง</option><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option>
      </select>
      <label htmlFor="practice-disposition">Disposition</label><select id="practice-disposition" value={draft.disposition} onChange={(event) => updateDraft({ disposition: event.target.value })}>
        <option value="">เลือกข้อสรุป</option><option value="true_positive">True positive</option><option value="false_positive">False positive</option><option value="undetermined">Undetermined</option>
      </select>
      <label htmlFor="practice-reason">เหตุผล หลักฐานที่รองรับ และสิ่งที่ยังไม่ทราบ</label><textarea id="practice-reason" value={draft.reason} maxLength={2000} rows={5} onChange={(event) => updateDraft({ reason: event.target.value })} />
      <p>ร่างอยู่ใน memory ของหน้านี้เท่านั้น เปลี่ยนเคสแล้วกลับมาดูได้ แต่รีเฟรชหรือออกจากหน้านี้จะหาย</p>
      <button type="button" onClick={() => setChecked(currentCase.id)}>ตรวจความครบของร่าง (ไม่ให้คะแนน)</button>
      {checked === currentCase.id && <div role="status" className="lesson-explanation">{missing.length
        ? <><p>ยังขาดข้อมูล:</p><ul>{missing.map((item) => <li key={String(item)}>{item}</li>)}</ul></>
        : <p>กรอกช่องที่จำเป็นครบแล้ว แต่ยังไม่ได้ตรวจความถูกต้อง ไม่ใช่ AI feedback และไม่ใช่ผลสอบผ่าน ตรวจว่าหลักฐานรองรับข้อสรุปจริงก่อนส่งในระบบจริง</p>}</div>}
    </fieldset>
    <section className="curriculum-guide" aria-labelledby="practice-guide-title">
      <h3 id="practice-guide-title">ต้องการคำอธิบายเพิ่ม?</h3>
      <p>ตอนฝึกเปิดคู่มือได้ ตอนสอบก่อนส่งจะไม่มีส่วนนี้ ปุ่มด้านล่างเลือกข้อความที่เขียนไว้ใน JSON แบบตายตัว ไม่ใช่การค้น RAG หรือคำตอบจาก AI</p>
      <div className="demo-actions"><button type="button" className="button-secondary" aria-expanded={guide === currentCase.id} onClick={() => setGuide(guide === currentCase.id ? null : currentCase.id)}>เปิดคำแนะนำจากบทเรียน</button><button type="button" disabled>ถาม AI — ยังไม่เชื่อม Dify</button></div>
      {guide === currentCase.id && <div className="lesson-explanation">{lessons.map((lesson) => <article key={lesson.id}><h4>{lesson.title}</h4><p>{lesson.steps[0].explanation}</p><p><strong>ข้อจำกัด:</strong> {lesson.steps[0].limitation}</p><Link href={trainingLink(lesson.id)}>อ่านบทเรียนอ้างอิง: {lesson.title}</Link></article>)}</div>}
    </section>
  </section>;
}
