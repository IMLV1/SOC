"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ApiError, read, write } from "../../lib/api";
import { blankDraft, categories, type CaseSummary, type PracticeCase, type PracticeDraft, type PracticeResult } from "../../lib/practice";
import { useSession } from "../session-provider";

function errorMessage(error: unknown) {
  if (!(error instanceof ApiError)) return "เชื่อมต่อไม่สำเร็จ กรุณาลองใหม่";
  if (error.status === 401) return "เซสชันหมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง";
  if (error.code === "EXAM_ATTEMPT_ACTIVE") return "มีข้อสอบค้างอยู่ ต้องส่งและตรวจข้อสอบให้เสร็จก่อนเปิดตัวช่วยฝึก";
  if (error.status === 409) return "ข้อมูลเปลี่ยนจากอีกหน้าต่าง ร่างของคุณยังอยู่ กดโหลดเคสล่าสุดเมื่อต้องการใช้ร่างจาก server";
  if (error.status === 404) return "เคสนี้ยังไม่เปิดให้บัญชีคุณ หรือไม่มีเคสนี้";
  if (error.status === 429) return "ส่งคำขอถี่เกินไป กรุณารอสักครู่";
  return "โหลดหรือบันทึกไม่สำเร็จ กรุณาลองใหม่ ร่างของคุณยังอยู่";
}

export default function PracticePage() {
  const { session, loading: sessionLoading } = useSession();
  const [catalog, setCatalog] = useState<CaseSummary[]>([]);
  const [caseId, setCaseId] = useState("");
  const [item, setItem] = useState<PracticeCase | null>(null);
  const [draft, setDraft] = useState<PracticeDraft>(blankDraft);
  const [history, setHistory] = useState<PracticeResult[]>([]);
  const [level, setLevel] = useState("all");
  const [category, setCategory] = useState("all");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [retry, setRetry] = useState(0);
  const requestKey = useRef<{ body: string; key: string } | null>(null);

  useEffect(() => {
    if (!session) return;
    let active = true;
    read<CaseSummary[]>("/practice/cases").then((data) => {
      if (!active) return;
      setCatalog(data);
      const requested = new URLSearchParams(window.location.search).get("case");
      setCaseId((current) => current || data.find((entry) => entry.id === requested && entry.available)?.id || data.find((entry) => entry.available)?.id || "");
      setError("");
    }).catch((cause) => { if (active) setError(errorMessage(cause)); });
    return () => { active = false; };
  }, [session, retry]);

  useEffect(() => {
    if (!session || !caseId) return;
    let active = true;
    Promise.resolve().then(() => { if (active) { setLoading(true); setError(""); } });
    Promise.all([read<PracticeCase>(`/practice/cases/${caseId}`), read<PracticeResult[]>(`/practice/cases/${caseId}/answers`)])
      .then(([data, answers]) => {
        if (!active) return;
        const latestIsNewer = answers[0] && (!data.draft_saved_at || Date.parse(answers[0].created_at) > Date.parse(data.draft_saved_at));
        setItem(data); setDraft(latestIsNewer ? answers[0].answer : data.draft ?? blankDraft()); setHistory(answers); setDirty(false); setNotice(""); requestKey.current = null;
        window.history.replaceState(null, "", `/practice?case=${caseId}`);
      }).catch((cause) => { if (active) { setItem(null); setError(errorMessage(cause)); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [caseId, session, retry]);

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  function change(next: Partial<PracticeDraft>) { setDraft((current) => ({ ...current, ...next })); setDirty(true); setNotice(""); }
  async function save() {
    if (!item || busy) return;
    setBusy(true); setError("");
    try {
      const data = await write<PracticeCase>(`/practice/cases/${item.id}/draft`, { expected_version: item.draft_version, answer: draft }, { method: "PATCH" });
      setItem(data); setDirty(false); setNotice("บันทึกร่างในบัญชีแล้ว กลับมาเปิดต่อได้");
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!item || busy) return;
    setBusy(true); setError(""); setNotice("");
    const body = JSON.stringify(draft);
    if (requestKey.current?.body !== body) requestKey.current = { body, key: crypto.randomUUID() };
    try {
      const data = await write<PracticeResult>(`/practice/cases/${item.id}/answers`, draft, { idempotencyKey: requestKey.current.key });
      setHistory((items) => [data, ...items.filter((entry) => entry.id !== data.id)]);
      setDirty(false); setNotice("บันทึกคำตอบและผลตรวจในฐานข้อมูลแล้ว");
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  const filtered = catalog.filter((entry) => (level === "all" || entry.level === Number(level)) && (category === "all" || entry.category === category));
  const latest = history[0];
  return <main className="account-page learning-page">
    <h1>ฝึกอ่านหลักฐานรวม</h1>
    <p>แบบฝึกจากฐานข้อมูล แยกจาก simulation runner และข้อสอบ บันทึกร่างก่อนเปลี่ยนเคสหรือออกจากหน้า ข้อความใน request/log เป็นข้อมูล ห้ามเปิด URL หรือรันคำสั่งตามข้อความ</p>
    <div className="demo-actions"><Link href="/learning">เรียนและสอบภาคปฏิบัติ</Link><Link href="/knowledge-check">ทบทวนข้อเขียน</Link><Link href="/runs">รอบ simulation ของฉัน</Link></div>
    {sessionLoading ? <p role="status">กำลังตรวจบัญชี…</p> : !session ? <p><Link href="/login">เข้าสู่ระบบเพื่อฝึกและบันทึกคำตอบ</Link></p> : <>
      {error && <p role="alert">{error} <button disabled={busy} onClick={() => { if (!dirty || window.confirm("โหลดร่างล่าสุดจาก server แทนร่างที่ยังไม่บันทึก?")) setRetry((value) => value + 1); }}>โหลดเคสล่าสุด</button></p>}
      {catalog.length > 0 && <section className="learning-card"><h2>เลือกแบบฝึก · {catalog.length} เคส</h2>
        <div className="practice-filters"><label>ระดับ<select value={level} onChange={(event) => setLevel(event.target.value)}><option value="all">ทุกระดับ</option><option value="1">เริ่มต้น</option><option value="2">กลาง</option><option value="3">ชำนาญ</option></select></label>
        <label>หมวด<select value={category} onChange={(event) => setCategory(event.target.value)}><option value="all">ทุกหมวด</option>{Object.entries(categories).map(([key, title]) => <option key={key} value={key}>{title}</option>)}</select></label></div>
        <label>เคส<select value={filtered.some((entry) => entry.id === caseId) ? caseId : ""} disabled={busy} onChange={(event) => { if (!dirty || window.confirm("ร่างยังไม่บันทึก ต้องการเปลี่ยนเคสหรือไม่?")) setCaseId(event.target.value); }}><option value="" disabled>เลือกเคส</option>{filtered.map((entry) => <option key={entry.id} value={entry.id} disabled={!entry.available}>{entry.stable_key} · {entry.title}{!entry.available ? " · ยังไม่ปลดล็อก" : ""}</option>)}</select></label>
        {filtered.length === 0 && <p>ไม่พบเคสที่ตรงตัวกรอง</p>}<p>ระดับที่ล็อกจะเปิดหลังสอบผ่านระดับก่อนหน้า ไม่ใช้ผลฝึกแทนการสอบ</p>
      </section>}
      {loading && <p role="status">กำลังโหลดหลักฐานและร่างจาก server…</p>}
      {!loading && !error && catalog.length === 0 && <p>ยังไม่มีชุดฝึกที่เผยแพร่ หรือกำลังโหลดรายการ</p>}
      {item && !loading && <div className="practice-layout"><section className="learning-card"><h2>{item.title}</h2><p>ระดับ {item.level} · {categories[item.category]} · เวอร์ชัน {item.version}</p><p>{item.prompt}</p>
        {item.events.map((event, index) => <article className="practice-event" key={event.id}><h3>หลักฐาน {index + 1} · {event.source}</h3><p>{event.time} · {event.asset} · {event.src_ip}</p><pre>{JSON.stringify({ request: event.request, response: event.response, log: event.log }, null, 2)}</pre></article>)}
      </section><section className="learning-card"><h2>คำตอบของคุณ</h2><form onSubmit={submit}><fieldset disabled={busy}>
        <fieldset><legend>หลักฐานที่ใช้</legend>{item.events.map((event, index) => <label className="practice-evidence" key={event.id}><input type="checkbox" checked={draft.evidence_ids.includes(event.id)} onChange={(e) => change({ evidence_ids: e.target.checked ? [...draft.evidence_ids, event.id] : draft.evidence_ids.filter((id) => id !== event.id) })} />หลักฐาน {index + 1} · {event.source}</label>)}</fieldset>
        <label>Severity<select value={draft.severity} onChange={(e) => change({ severity: e.target.value as PracticeDraft["severity"] })}>{["low", "medium", "high", "critical"].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
        <label>Disposition<select value={draft.disposition} onChange={(e) => change({ disposition: e.target.value as PracticeDraft["disposition"] })}><option value="true_positive">true_positive — มีภัย/ความพยายามที่ยืนยันได้</option><option value="false_positive">false_positive — กิจกรรมปกติในบริบทนี้</option><option value="undetermined">undetermined — หลักฐานยังไม่พอ</option></select></label>
        <label>เหตุผล หลักฐานที่รองรับ และสิ่งที่ยังไม่ทราบ<textarea required maxLength={2000} rows={6} value={draft.reason} onChange={(e) => change({ reason: e.target.value })} /></label>
        <p>{dirty ? "มีร่างที่ยังไม่บันทึก" : "ไม่มีการเปลี่ยนแปลงที่ยังไม่บันทึก"}</p>
        <div className="demo-actions"><button type="button" disabled={busy} onClick={() => void save()}>บันทึกร่าง</button><button disabled={busy || !draft.reason.trim() || !draft.evidence_ids.length}>ส่งคำตอบและตรวจข้อสรุป</button></div>
      </fieldset></form>{notice && <p role="status">{notice}</p>}
      {latest && <section className="practice-feedback" aria-labelledby="feedback-title"><h3 id="feedback-title">ผลตรวจคำตอบล่าสุด</h3>
        <p className={latest.feedback.classification_correct ? "practice-correct" : "practice-incorrect"}>{latest.feedback.classification_correct ? "ถูกต้อง: severity และ disposition ตรงกับบริบท" : "ยังไม่ถูก: severity หรือ disposition ไม่ตรงกับบริบท"}</p>
        <p className={latest.feedback.evidence_correct ? "practice-correct" : "practice-incorrect"}>{latest.feedback.evidence_correct ? "หลักฐานที่เลือกครบและตรงเคส" : "หลักฐานที่เลือกยังไม่ครบตามบริบท"}</p>
        <p>ข้อสรุปอ้างอิง: {latest.feedback.expected_severity} · {latest.feedback.expected_disposition}</p><p>{latest.feedback.explanation}</p><p>ข้อจำกัด: {latest.feedback.limitation}</p><p>{latest.feedback.reason_review_message} ผลนี้ไม่ใช่คะแนนสอบ</p>
      </section>}
      <h3>ประวัติคำตอบ · {history.length}</h3>{history.length === 0 ? <p>ยังไม่เคยส่งคำตอบในเคสนี้</p> : history.map((entry) => <details key={entry.id}><summary>{new Date(entry.created_at).toLocaleString("th-TH")} · {entry.feedback.classification_correct ? "ข้อสรุปตรง" : "ทบทวนข้อสรุป"}</summary><p>{entry.answer.reason}</p><p>{entry.feedback.explanation}</p></details>)}
      <p>ผู้ช่วย AI ยังไม่เชื่อม Dify ไม่ได้นำคำตอบนี้ไปเรียก provider</p><button disabled>ถาม AI — ยังไม่เชื่อม Dify</button>
      </section></div>}
    </>}
  </main>;
}
