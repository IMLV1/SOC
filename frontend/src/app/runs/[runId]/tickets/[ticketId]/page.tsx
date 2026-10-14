"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ApiError, read, write } from "../../../../../lib/api";
import type { Assessment, Event, Note, Run, Ticket } from "../../../../../lib/run-types";
import { useSession } from "../../../../session-provider";

export default function TicketPage() {
  const { runId, ticketId } = useParams<{ runId: string; ticketId: string }>();
  const isNew = ticketId === "new";
  const router = useRouter();
  const { session, loading: sessionLoading } = useSession();
  const [run, setRun] = useState<Run | null>(null);
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [title, setTitle] = useState("");
  const [severity, setSeverity] = useState("low");
  const [status, setStatus] = useState("open");
  const [disposition, setDisposition] = useState("");
  const [reason, setReason] = useState("");
  const [selectedEvidence, setSelectedEvidence] = useState<string[]>([]);
  const [newNote, setNewNote] = useState("");
  const [noteDrafts, setNoteDrafts] = useState<Record<string, string>>({});
  const load = useCallback(async (preserveDraft = false) => {
    try {
      const currentRun = await read<Run>(`/runs/${runId}`);
      setRun(currentRun);
      if (isNew) {
        const released = await read<Event[]>(`/runs/${runId}/events?limit=100`);
        setEvents(released);
      } else {
        const [currentTicket, currentNotes, history] = await Promise.all([
          read<Ticket>(`/runs/${runId}/tickets/${ticketId}`),
          read<Note[]>(`/runs/${runId}/tickets/${ticketId}/notes?deleted=true`),
          read<Assessment[]>(`/runs/${runId}/tickets/${ticketId}/assessments`),
        ]);
        setTicket(currentTicket); setNotes(currentNotes); setAssessments(history);
        if (!preserveDraft) {
          setTitle(currentTicket.title); setSeverity(currentTicket.severity);
          setStatus(currentTicket.status);
          setDisposition("");
          setNoteDrafts(Object.fromEntries(currentNotes.map(item => [item.id, item.body])));
        }
      }
      setMessage("");
    } catch (error) {
      setMessage(error instanceof ApiError && error.status === 401 ? "เซสชันหมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง" : "โหลด ticket ไม่สำเร็จ");
    } finally { setLoading(false); }
  }, [runId, ticketId, isNew]);
  useEffect(() => {
    if (!session) return;
    const timer = setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
  }, [session, load]);
  const mutable = run && ["running", "paused", "reviewing"].includes(run.status);
  function errorMessage(error: unknown) {
    if (error instanceof ApiError && error.status === 409) return "ข้อมูลถูกแก้ไขหรือรอบถูกล็อกแล้ว ร่างของคุณยังอยู่ กดโหลดเวอร์ชันล่าสุดเพื่อตรวจเปรียบเทียบ";
    if (error instanceof ApiError && error.status === 401) return "เซสชันหมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง";
    return "บันทึกไม่สำเร็จ กรุณาตรวจข้อมูลและลองใหม่";
  }
  async function createTicket() {
    setBusy(true); setMessage("");
    try {
      const created = await write<Ticket>(`/runs/${runId}/tickets`,
        { title, severity, evidence_ids: selectedEvidence, reason },
        { idempotencyKey: crypto.randomUUID() });
      router.replace(`/runs/${runId}/tickets/${created.id}`);
    } catch (error) { setMessage(errorMessage(error)); } finally { setBusy(false); }
  }
  async function saveTicket() {
    if (!ticket) return;
    setBusy(true); setMessage("");
    try {
      const updated = await write<Ticket>(`/runs/${runId}/tickets/${ticket.id}`,
        { expected_version: ticket.version, title, severity, status,
          ...(disposition ? { disposition } : {}), reason }, { method: "PATCH" });
      setTicket(updated); setAssessments(await read<Assessment[]>(`/runs/${runId}/tickets/${ticket.id}/assessments`));
      setReason(""); setDisposition("");
    } catch (error) { setMessage(errorMessage(error)); } finally { setBusy(false); }
  }
  async function changeDeleted(restore: boolean) {
    if (!ticket) return;
    if (!restore && !window.confirm("ลบ ticket แบบ soft delete? กู้คืนได้ก่อนรอบถูกล็อก")) return;
    setBusy(true); setMessage("");
    try {
      const updated = await write<Ticket>(`/runs/${runId}/tickets/${ticket.id}${restore ? "/restore" : ""}`,
        { expected_version: ticket.version, reason }, { method: restore ? "POST" : "DELETE" });
      setTicket(updated); setReason("");
    } catch (error) { setMessage(errorMessage(error)); } finally { setBusy(false); }
  }
  async function addNote() {
    if (!ticket) return;
    setBusy(true); setMessage("");
    try {
      const item = await write<Note>(`/runs/${runId}/tickets/${ticket.id}/notes`,
        { body: newNote, evidence_ids: ticket.evidence_ids },
        { idempotencyKey: crypto.randomUUID() });
      setNotes(current => [...current, item]); setNewNote("");
      setNoteDrafts(current => ({ ...current, [item.id]: item.body }));
    } catch (error) { setMessage(errorMessage(error)); } finally { setBusy(false); }
  }
  async function changeNote(note: Note, action: "edit" | "delete" | "restore") {
    if (!ticket) return;
    setBusy(true); setMessage("");
    try {
      const path = `/runs/${runId}/tickets/${ticket.id}/notes/${note.id}`;
      const updated = await write<Note>(path + (action === "restore" ? "/restore" : ""),
        action === "edit" ? { expected_version: note.version, body: noteDrafts[note.id],
                               evidence_ids: note.evidence_ids, reason: reason || "แก้ไขบันทึก" } :
                            { expected_version: note.version, reason: reason || "เปลี่ยนสถานะบันทึก" },
        { method: action === "edit" ? "PATCH" : action === "delete" ? "DELETE" : "POST" });
      setNotes(current => current.map(item => item.id === note.id ? updated : item));
      setReason("");
    } catch (error) { setMessage(errorMessage(error)); } finally { setBusy(false); }
  }
  return <main className="run-shell">
    <div className="run-topline"><Link href={`/runs/${runId}`}>กลับไปรอบฝึก</Link><span>03 — Investigation</span></div>
    <h1>{isNew ? "สร้าง ticket" : ticket?.title || "Ticket"}</h1>
    {sessionLoading ? <p role="status">กำลังตรวจบัญชี…</p> : !session ? <p><Link href="/login">เข้าสู่ระบบเพื่อสืบสวน</Link></p> : <>
      {loading && <p role="status">กำลังโหลด…</p>}
      {message && <p role="alert" className="run-alert">{message} {!isNew && <button type="button" onClick={() => void load(true)}>โหลดเวอร์ชันล่าสุด</button>}</p>}
      {run && <p className="run-muted">รอบ {run.status} · {mutable ? "แก้ไขได้" : "อ่านได้อย่างเดียวหลังเริ่มปิดรอบ"}</p>}
      {isNew ? <section className="run-panel">
        <label>หัวข้อ<input value={title} onChange={event => setTitle(event.target.value)} maxLength={120} /></label>
        <label>ความรุนแรง<select value={severity} onChange={event => setSeverity(event.target.value)}>
          {["low", "medium", "high", "critical"].map(value => <option key={value}>{value}</option>)}
        </select></label>
        <fieldset><legend>เลือกหลักฐานอย่างน้อยหนึ่งรายการ</legend>{events.map(item => <label key={item.id}>
          <input type="checkbox" checked={selectedEvidence.includes(item.id)} onChange={event => setSelectedEvidence(current =>
            event.target.checked ? [...current, item.id] : current.filter(id => id !== item.id))} />
          #{item.release_seq} · {item.source} · {item.asset_id}
        </label>)}</fieldset>
        <label>เหตุผล<textarea value={reason} onChange={event => setReason(event.target.value)} maxLength={2000} /></label>
        <button disabled={!mutable || busy || !title.trim() || !reason.trim() || selectedEvidence.length === 0}
                onClick={() => void createTicket()}>สร้าง ticket</button>
      </section> : ticket && <>
        <section className="run-panel"><h2>ข้อสรุปของผู้วิเคราะห์</h2>
          <p>ต้นทาง {ticket.origin} · severity {ticket.severity} · สถานะ {ticket.status} · version {ticket.version}</p>
          <p>หลักฐาน {ticket.evidence_ids.length} รายการ: {ticket.evidence_ids.join(", ")}</p>
          {ticket.deleted_at && <p className="run-alert">Ticket ถูกลบแบบ soft delete · {ticket.deleted_at}</p>}
          <label>หัวข้อ<input value={title} onChange={event => setTitle(event.target.value)} maxLength={120} disabled={!mutable || !!ticket.deleted_at} /></label>
          <label>ความรุนแรง<select value={severity} onChange={event => setSeverity(event.target.value)} disabled={!mutable || !!ticket.deleted_at}>
            {["low", "medium", "high", "critical"].map(value => <option key={value}>{value}</option>)}
          </select></label>
          <label>สถานะ<select value={status} onChange={event => setStatus(event.target.value)} disabled={!mutable || !!ticket.deleted_at}>
            {["open", "investigating", "resolved", "closed"].map(value => <option key={value}>{value}</option>)}
          </select></label>
          <label>ประเมิน<select value={disposition} onChange={event => setDisposition(event.target.value)} disabled={!mutable || !!ticket.deleted_at}>
            <option value="">ยังไม่สรุปใหม่</option><option value="true_positive">ภัยจริง</option>
            <option value="false_positive">ไม่ใช่ภัย</option><option value="undetermined">ยังไม่แน่ใจ</option>
          </select></label>
          <label>เหตุผล<textarea value={reason} onChange={event => setReason(event.target.value)} maxLength={2000} disabled={!mutable} /></label>
          <div className="run-button-row"><button disabled={!mutable || busy || !!ticket.deleted_at || !reason.trim()} onClick={() => void saveTicket()}>บันทึก</button>
            {ticket.deleted_at ? <button disabled={!mutable || busy || !reason.trim()} onClick={() => void changeDeleted(true)}>กู้คืน</button> :
              <button disabled={!mutable || busy || !reason.trim()} onClick={() => void changeDeleted(false)}>ลบแบบกู้คืนได้</button>}</div>
        </section>
        <div className="evidence-layout"><section className="run-panel"><h2>ประวัติการประเมิน</h2>
          {assessments.length === 0 ? <p>ยังไม่มีข้อสรุป</p> : <ol>{assessments.map(item =>
            <li key={item.id}>ครั้งที่ {item.revision} · {item.disposition} · {item.reason}</li>)}</ol>}
        </section><section className="run-panel"><h2>บันทึก</h2>
          {notes.length === 0 ? <p>ยังไม่มีบันทึก</p> : notes.map(note => <div className="note-card" key={note.id}>
            <p>Version {note.version} · {note.deleted_at ? "ถูกลบ" : "ใช้งาน"} · หลักฐาน {note.evidence_ids.length}</p>
            <textarea value={noteDrafts[note.id] ?? note.body} disabled={!mutable || !!note.deleted_at}
                      onChange={event => setNoteDrafts(current => ({ ...current, [note.id]: event.target.value }))} />
            <div className="run-button-row">{note.deleted_at ? <button disabled={!mutable || busy} onClick={() => void changeNote(note, "restore")}>กู้คืน</button> : <>
              <button disabled={!mutable || busy} onClick={() => void changeNote(note, "edit")}>แก้บันทึก</button>
              <button disabled={!mutable || busy} onClick={() => void changeNote(note, "delete")}>ลบบันทึก</button></>}
            <Link href={`/runs/${runId}/tickets/${ticket.id}/notes/${note.id}/versions`}>ดูประวัติ</Link></div>
          </div>)}
          <label>บันทึกใหม่<textarea value={newNote} onChange={event => setNewNote(event.target.value)} maxLength={2000} disabled={!mutable || !!ticket.deleted_at} /></label>
          <button disabled={!mutable || busy || !!ticket.deleted_at || !newNote.trim()} onClick={() => void addNote()}>เพิ่มบันทึก</button>
        </section></div>
      </>}
    </>}
  </main>;
}
