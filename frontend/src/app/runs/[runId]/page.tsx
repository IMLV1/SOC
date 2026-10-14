"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ApiError, read, readPage, write } from "../../../lib/api";
import type { Alert, Analysis, Event, Run, Ticket } from "../../../lib/run-types";
import { useSession } from "../../session-provider";

const sources = ["", "authentication", "web", "file_access", "change_management", "baseline"];

export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const { session, loading: sessionLoading } = useSession();
  const [run, setRun] = useState<Run | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [selected, setSelected] = useState("");
  const [source, setSource] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const seq = useRef(0);
  useEffect(() => {
    const timer = setTimeout(() => {
      const query = new URLSearchParams(window.location.search);
      const chosenSource = query.get("source") || "";
      if (sources.includes(chosenSource)) setSource(chosenSource);
      setSelected(query.get("event") || "");
    }, 0);
    return () => clearTimeout(timer);
  }, []);
  useEffect(() => {
    if (!session || !runId) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    let delay = 2000;
    seq.current = 0;
    async function poll() {
      if (!active) return;
      if (document.hidden) { timer = setTimeout(poll, 2000); return; }
      try {
        const current = await read<Run>(`/runs/${runId}`);
        const query = new URLSearchParams({ after_seq: String(seq.current), limit: "100" });
        if (source) query.set("source", source);
        const [page, currentAlerts, currentTickets, currentAnalyses] = await Promise.all([
          readPage<Event[]>(`/runs/${runId}/events?${query}`),
          read<Alert[]>(`/runs/${runId}/alerts`),
          read<Ticket[]>(`/runs/${runId}/tickets`),
          read<Analysis[]>(`/runs/${runId}/analyses`),
        ]);
        if (!active) return;
        setRun(current);
        setAlerts(currentAlerts); setTickets(currentTickets); setAnalyses(currentAnalyses);
        if (page.data.length) {
          seq.current = Math.max(seq.current, ...page.data.map(item => item.release_seq));
          setEvents(previous => {
            const ids = new Set(previous.map(item => item.id));
            return [...previous, ...page.data.filter(item => !ids.has(item.id))];
          });
        }
        setError(""); delay = 2000; setLoading(false);
      } catch (cause) {
        if (!active) return;
        setError(cause instanceof ApiError && cause.status === 401 ? "เซสชันหมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง" : "โหลดข้อมูลรอบฝึกไม่สำเร็จ ระบบจะลองใหม่");
        delay = Math.min(delay * 2, 30000); setLoading(false);
      }
      if (active) timer = setTimeout(poll, delay);
    }
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, [session, runId, source]);
  function chooseEvent(id: string) {
    setSelected(id);
    const query = new URLSearchParams(window.location.search);
    query.set("event", id);
    window.history.replaceState(null, "", `?${query}`);
  }
  function chooseSource(value: string) {
    seq.current = 0;
    setEvents([]);
    setSelected("");
    setSource(value);
    const query = new URLSearchParams(window.location.search);
    if (value) query.set("source", value); else query.delete("source");
    query.delete("event");
    window.history.replaceState(null, "", `?${query}`);
  }
  async function control(action: "pause" | "resume") {
    if (!run) return;
    setBusy(true); setError("");
    try { setRun(await write<Run>(`/runs/${runId}/${action}`, { expected_version: run.version })); }
    catch (cause) {
      setError(cause instanceof ApiError && cause.status === 409 ? "สถานะรอบเปลี่ยนไปแล้ว กำลังโหลดข้อมูลล่าสุด" : "เปลี่ยนสถานะไม่สำเร็จ");
      try { setRun(await read<Run>(`/runs/${runId}`)); } catch { /* polling retries */ }
    } finally { setBusy(false); }
  }
  async function retryAnalysis(item: Analysis) {
    setBusy(true); setError("");
    try {
      const retry = await write<Analysis>(`/runs/${runId}/analyses/${item.id}/retry`,
        { expected_version: item.version }, { idempotencyKey: crypto.randomUUID() });
      setAnalyses(current => [retry, ...current]);
    } catch (cause) {
      setError(cause instanceof ApiError && cause.status === 409
        ? "คำวิเคราะห์เปลี่ยนสถานะแล้ว กรุณารอข้อมูลล่าสุด" : "ส่งคำขอวิเคราะห์ซ้ำไม่สำเร็จ");
    } finally { setBusy(false); }
  }
  const event = events.find(item => item.id === selected) ?? null;
  return <main className="run-shell">
    <div className="run-topline"><Link href="/runs">รอบฝึก</Link><span>02 — Event explorer</span></div>
    <h1>สำรวจเหตุการณ์</h1>
    {sessionLoading ? <p role="status">กำลังตรวจบัญชี…</p> : !session ? <p><Link href="/login">เข้าสู่ระบบเพื่อดูหลักฐาน</Link></p> : <>
      {loading ? <p role="status">กำลังโหลดรอบและเหตุการณ์…</p> : run && <section className="run-summary" aria-label="สถานะรอบฝึก">
        <div><span>สถานะ</span><strong>{run.status}</strong></div>
        <div><span>เวลาจำลอง</span><strong>{(run.elapsed_ms / 1000).toFixed(1)} / {(run.duration_ms / 1000).toFixed(0)} วินาที</strong></div>
        <div><span>AI</span><strong>{run.analysis_mode} · ผลจำลอง ไม่ใช่คะแนน</strong></div>
        <div className="run-actions">{run.status === "running" && <button disabled={busy} onClick={() => void control("pause")}>พักรอบ</button>}
          {run.status === "paused" && <button disabled={busy} onClick={() => void control("resume")}>ทำต่อ</button>}</div>
      </section>}
      {error && <p role="alert" className="run-alert">{error}</p>}
      <div className="evidence-layout">
        <section className="run-panel" aria-labelledby="events-title">
          <div className="run-section-head"><h2 id="events-title">เหตุการณ์ที่ปล่อยแล้ว</h2><span>{events.length} รายการ</span></div>
          <label>แหล่งข้อมูล <select value={source} onChange={event => chooseSource(event.target.value)}>
            {sources.map(item => <option key={item} value={item}>{item || "ทั้งหมด"}</option>)}
          </select></label>
          {events.length === 0 ? <p>ยังไม่มีเหตุการณ์ที่ตรงตัวกรอง ระบบจะตรวจอีกครั้งอัตโนมัติ</p> :
            <ol className="event-list">{events.map(item => <li key={item.id}>
              <button className={item.id === selected ? "selected" : ""} onClick={() => chooseEvent(item.id)}>
                <span className="event-number">{String(item.release_seq).padStart(2, "0")}</span>
                <span><strong>{item.source}</strong><small>{item.asset_id || "ไม่ระบุ asset"} · {item.username || "ไม่ระบุ user"}</small></span>
                <time>{new Date(item.event_time).toLocaleTimeString("th-TH")}</time>
              </button>
            </li>)}</ol>}
        </section>
        <section className="run-panel event-detail" aria-labelledby="detail-title">
          <h2 id="detail-title">หลักฐาน</h2>
          {!event ? <p>เลือกเหตุการณ์ทางซ้ายเพื่อดู request, response และ log</p> : <>
            <p>Event #{event.release_seq} · {event.source} · {event.src_ip || "ไม่ระบุ IP"}</p>
            <h3>Request</h3><pre>{JSON.stringify(event.request, null, 2)}</pre>
            <h3>Response</h3><pre>{JSON.stringify(event.response, null, 2)}</pre>
            <h3>Log</h3><pre>{JSON.stringify(event.log, null, 2)}</pre>
            <p className="run-muted">ตรวจ status และ event_type ก่อนสรุปผล การถูกบล็อกไม่ใช่หลักฐานว่าถูกเจาะสำเร็จ</p>
          </>}
        </section>
      </div>
      <div className="evidence-layout">
        <section className="run-panel" aria-labelledby="alerts-title">
          <h2 id="alerts-title">สัญญาณตรวจพบ</h2>
          {alerts.length === 0 ? <p>ยังไม่มี alert จาก rule หรือ anomaly</p> :
            <ol className="run-list">{alerts.map(item => <li key={item.id}>
              <p><strong>{item.detector_type === "anomaly" ? "Anomaly" : "Rule"} · {item.severity}</strong> · {item.detector_version}</p>
              <p>{item.explanation}</p>
              <p>หลักฐาน {item.evidence_ids.length} รายการ · {item.ticket_id ? <Link href={`/runs/${runId}/tickets/${item.ticket_id}`}>เปิด ticket</Link> : "ยังไม่มี ticket"}</p>
            </li>)}</ol>}
        </section>
        <section className="run-panel" aria-labelledby="tickets-title">
          <h2 id="tickets-title">Ticket และคำวิเคราะห์</h2>
          <p><Link href={`/runs/${runId}/tickets/new`}>สร้าง ticket จากหลักฐาน</Link></p>
          {tickets.length === 0 ? <p>ยังไม่มี ticket</p> : <ol className="run-list">{tickets.map(item =>
            <li key={item.id}><Link href={`/runs/${runId}/tickets/${item.id}`}>{item.title} · {item.severity} · {item.status}</Link></li>)}</ol>}
          <h3>AI-assisted analysis</h3><p className="run-muted">โหมด mock เท่านั้น ไม่ใช่คะแนนหรือผล benchmark</p>
          {analyses.length === 0 ? <p>ยังไม่มีคำวิเคราะห์</p> : <ol className="run-list">{analyses.map(item => <li key={item.id}>
            <strong>{item.status}</strong> · {item.mode}{item.result && <p>{item.result.summary}</p>}
            {item.error_code && <p role="status">{item.error_code}</p>}
            {["failed", "timed_out", "invalid_output", "quota_exceeded"].includes(item.status) &&
              <button disabled={busy || !run || !["running", "paused", "reviewing"].includes(run.status)}
                onClick={() => void retryAnalysis(item)}>ลองวิเคราะห์ซ้ำ</button>}
          </li>)}</ol>}
        </section>
      </div>
    </>}
  </main>;
}
