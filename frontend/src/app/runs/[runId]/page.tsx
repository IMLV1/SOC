"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ApiError, read, readPage, write } from "../../../lib/api";
import type {
  Alert,
  Analysis,
  Event,
  Run,
  Ticket,
} from "../../../lib/run-types";
import type { FinishView } from "../../../lib/api-types";
import { useSession } from "../../session-provider";

const sources = [
  "",
  "authentication",
  "web",
  "file_access",
  "change_management",
  "baseline",
];

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
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [filtersReady, setFiltersReady] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [pollError, setPollError] = useState("");
  const [controlPending, setControlPending] = useState<"pause" | "resume" | null>(null);
  const seq = useRef(0);
  useEffect(() => {
    const timer = setTimeout(() => {
      const query = new URLSearchParams(window.location.search);
      const chosenSource = query.get("source") || "";
      if (sources.includes(chosenSource)) setSource(chosenSource);
      setSelected(query.get("event") || "");
      setFilters(
        Object.fromEntries(
          ["q", "asset_id", "username", "src_ip", "from", "to"].map((key) => [
            key,
            query.get(key) || "",
          ]),
        ),
      );
      setFiltersReady(true);
    }, 0);
    return () => clearTimeout(timer);
  }, []);
  useEffect(() => {
    if (!session || !runId || !filtersReady) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    let delay = 2000;
    let cursor: string | null = null;
    seq.current = 0;
    async function poll() {
      if (!active) return;
      if (document.hidden) {
        timer = setTimeout(poll, 2000);
        return;
      }
      try {
        const current = await read<Run>(`/runs/${runId}`);
        const query = new URLSearchParams({ limit: "50" });
        if (cursor) query.set("cursor", cursor);
        else query.set("after_seq", String(seq.current));
        for (const [key, value] of Object.entries(filters))
          if (value) query.set(key, value);
        if (source) query.set("source", source);
        const [page, currentAlerts, currentTickets, currentAnalyses] =
          await Promise.all([
            readPage<Event[]>(`/runs/${runId}/events?${query}`),
            read<Alert[]>(`/runs/${runId}/alerts`),
            read<Ticket[]>(`/runs/${runId}/tickets`),
            read<Analysis[]>(`/runs/${runId}/analyses`),
          ]);
        if (!active) return;
        cursor = page.meta.next_cursor ?? null;
        setRun((previous) =>
          !previous || current.version >= previous.version ? current : previous,
        );
        setAlerts(currentAlerts);
        setTickets(currentTickets);
        setAnalyses(currentAnalyses);
        if (page.data.length) {
          seq.current = Math.max(
            seq.current,
            ...page.data.map((item) => item.release_seq),
          );
          setEvents((previous) => {
            const ids = new Set(previous.map((item) => item.id));
            return [
              ...previous,
              ...page.data.filter((item) => !ids.has(item.id)),
            ];
          });
        }
        setPollError("");
        delay = cursor ? 0 : 2000;
        setLoading(false);
      } catch (cause) {
        if (!active) return;
        setPollError(
          cause instanceof ApiError && cause.status === 401
            ? "เซสชันหมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง"
            : cause instanceof ApiError && cause.status === 422
              ? "ตัวกรองไม่ถูกต้อง กรุณาตรวจรูปแบบ IP และเวลา UTC"
              : "โหลดข้อมูลรอบฝึกไม่สำเร็จ ระบบจะลองใหม่",
        );
        delay = Math.min(Math.max(delay, 2000) * 2, 30000);
        setLoading(false);
        if (
          cause instanceof ApiError &&
          [401, 403, 404, 422].includes(cause.status)
        )
          return;
      }
      if (active) timer = setTimeout(poll, delay);
    }
    timer = setTimeout(() => {
      setEvents([]);
      setAlerts([]);
      setTickets([]);
      setAnalyses([]);
      setRun(null);
      setLoading(true);
      void poll();
    }, 0);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [session, runId, source, filters, filtersReady]);
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
    if (value) query.set("source", value);
    else query.delete("source");
    query.delete("event");
    window.history.replaceState(null, "", `?${query}`);
  }
  function chooseFilter(key: string, value: string) {
    seq.current = 0;
    setEvents([]);
    setSelected("");
    setFilters((current) => ({ ...current, [key]: value }));
    const query = new URLSearchParams(window.location.search);
    if (value) query.set(key, value);
    else query.delete(key);
    query.delete("event");
    window.history.replaceState(null, "", `?${query}`);
  }
  async function control(action: "pause" | "resume") {
    if (!run) return;
    setBusy(true);
    setControlPending(action);
    setError("");
    try {
      let current = run;
      for (let attempt = 0; attempt < 5; attempt += 1) {
        try {
          setRun(
            await write<Run>(`/runs/${runId}/${action}`, {
              expected_version: current.version,
            }),
          );
          return;
        } catch (cause) {
          if (!(cause instanceof ApiError) || cause.status !== 409 || attempt === 4) {
            throw cause;
          }
          const latest = await read<Run>(`/runs/${runId}`);
          setRun(latest);
          const expectedStatus = action === "pause" ? "running" : "paused";
          if (latest.status !== expectedStatus) return;
          current = latest;
        }
      }
    } catch (cause) {
      setError(
        cause instanceof ApiError && cause.status === 409
          ? "สถานะรอบเปลี่ยนไปแล้ว กำลังโหลดข้อมูลล่าสุด"
          : cause instanceof ApiError && cause.status === 401
            ? "เซสชันหมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง"
            : cause instanceof ApiError && cause.code === "AUTH_REFRESH_PENDING"
              ? "กำลังต่ออายุเซสชัน กรุณาลองคำสั่งอีกครั้ง"
              : "เปลี่ยนสถานะไม่สำเร็จ กรุณาลองอีกครั้ง",
      );
      try {
        setRun(await read<Run>(`/runs/${runId}`));
      } catch {
        /* polling retries */
      }
    } finally {
      setBusy(false);
      setControlPending(null);
    }
  }
  async function finish() {
    if (!run) return;
    setBusy(true);
    setError("");
    try {
      const result = await write<FinishView>(`/runs/${runId}/finish`, {
        expected_version: run.version,
      });
      setRun(result);
    } catch (cause) {
      setError(
        cause instanceof ApiError && cause.status === 409
          ? "สถานะรอบเปลี่ยนไปแล้ว กำลังโหลดข้อมูลล่าสุด"
          : "ปิดรอบฝึกไม่สำเร็จ",
      );
      try {
        setRun(await read<Run>(`/runs/${runId}`));
      } catch {
        /* polling retries */
      }
    } finally {
      setBusy(false);
    }
  }
  async function retryAnalysis(item: Analysis) {
    setBusy(true);
    setError("");
    try {
      const retry = await write<Analysis>(
        `/runs/${runId}/analyses/${item.id}/retry`,
        { expected_version: item.version },
        { idempotencyKey: crypto.randomUUID() },
      );
      setAnalyses((current) => [retry, ...current]);
    } catch (cause) {
      setError(
        cause instanceof ApiError && cause.status === 409
          ? "คำวิเคราะห์เปลี่ยนสถานะแล้ว กรุณารอข้อมูลล่าสุด"
          : "ส่งคำขอวิเคราะห์ซ้ำไม่สำเร็จ",
      );
    } finally {
      setBusy(false);
    }
  }
  const event = events.find((item) => item.id === selected) ?? null;
  return (
    <main className="run-shell">
      <div className="run-topline">
        <Link href="/runs">รอบฝึก</Link>
        <span>02 — Event explorer</span>
      </div>
      <h1>สำรวจเหตุการณ์</h1>
      {sessionLoading ? (
        <p role="status">กำลังตรวจบัญชี…</p>
      ) : !session ? (
        <p>
          <Link href="/login">เข้าสู่ระบบเพื่อดูหลักฐาน</Link>
        </p>
      ) : (
        <>
          {loading ? (
            <p role="status">กำลังโหลดรอบและเหตุการณ์…</p>
          ) : (
            run && (
              <section className="run-summary" aria-label="สถานะรอบฝึก">
                <div>
                  <span>สถานะ</span>
                  <strong>{run.status}</strong>
                </div>
                <div>
                  <span>เวลาจำลอง</span>
                  <strong>
                    {(run.elapsed_ms / 1000).toFixed(1)} /{" "}
                    {(run.duration_ms / 1000).toFixed(0)} วินาที
                  </strong>
                </div>
                <div>
                  <span>AI</span>
                  <strong>
                    {run.analysis_mode === "mock"
                      ? "mode=mock · ผลจำลอง ไม่ใช่คะแนน"
                      : "mode=real · ใช้ข้อมูลจำลองในการฝึกเท่านั้น"}
                  </strong>
                </div>
                <div className="run-actions">
                  {run.status === "running" && (
                    <button
                      disabled={busy}
                      onClick={() => void control("pause")}
                    >
                      {controlPending === "pause" ? "กำลังพักรอบ…" : "พักรอบ"}
                    </button>
                  )}
                  {run.status === "paused" && (
                    <button
                      disabled={busy}
                      onClick={() => void control("resume")}
                    >
                      {controlPending === "resume" ? "กำลังทำต่อ…" : "ทำต่อ"}
                    </button>
                  )}
                  {["running", "paused", "reviewing"].includes(run.status) && (
                    <button disabled={busy} onClick={() => void finish()}>
                      จบรอบและประเมินผล
                    </button>
                  )}
                  {["completing", "completed"].includes(run.status) && (
                    <Link href={`/runs/${runId}/evaluation`}>ดูผลประเมิน</Link>
                  )}
                </div>
              </section>
            )
          )}
          {(error || pollError) && (
            <p role="alert" className="run-alert">
              {error || pollError}
            </p>
          )}
          <div className="evidence-layout">
            <section className="run-panel" aria-labelledby="events-title">
              <div className="run-section-head">
                <h2 id="events-title">เหตุการณ์ที่ปล่อยแล้ว</h2>
                <span>{events.length} รายการ</span>
              </div>
              <label>
                แหล่งข้อมูล{" "}
                <select
                  value={source}
                  onChange={(event) => chooseSource(event.target.value)}
                >
                  {sources.map((item) => (
                    <option key={item} value={item}>
                      {item || "ทั้งหมด"}
                    </option>
                  ))}
                </select>
              </label>
              <div className="event-filters">
                {[
                  ["q", "คำค้น"],
                  ["asset_id", "Asset"],
                  ["username", "บัญชีในหลักฐาน"],
                  ["src_ip", "Source IP"],
                  ["from", "ตั้งแต่ (UTC ISO 8601)"],
                  ["to", "ก่อน (UTC ISO 8601)"],
                ].map(([key, label]) => (
                  <label key={key}>
                    {label}
                    <input
                      value={filters[key] || ""}
                      maxLength={key === "q" ? 200 : 254}
                      onChange={(event) =>
                        chooseFilter(key, event.target.value)
                      }
                    />
                  </label>
                ))}
              </div>
              {events.length === 0 ? (
                <p>
                  ยังไม่มีเหตุการณ์ที่ตรงตัวกรอง ระบบจะตรวจอีกครั้งอัตโนมัติ
                </p>
              ) : (
                <ol className="event-list">
                  {events.map((item) => (
                    <li key={item.id}>
                      <button
                        className={item.id === selected ? "selected" : ""}
                        onClick={() => chooseEvent(item.id)}
                      >
                        <span className="event-number">
                          {String(item.release_seq).padStart(2, "0")}
                        </span>
                        <span>
                          <strong>{item.source}</strong>
                          <small>
                            {item.asset_id || "ไม่ระบุ asset"} ·{" "}
                            {item.username || "ไม่ระบุ user"}
                          </small>
                        </span>
                        <time>
                          {new Date(item.event_time).toLocaleTimeString(
                            "th-TH",
                          )}
                        </time>
                      </button>
                    </li>
                  ))}
                </ol>
              )}
            </section>
            <section
              className="run-panel event-detail"
              aria-labelledby="detail-title"
            >
              <h2 id="detail-title">หลักฐาน</h2>
              {!event ? (
                <p>เลือกเหตุการณ์ทางซ้ายเพื่อดู request, response และ log</p>
              ) : (
                <>
                  <p>
                    Event #{event.release_seq} · {event.source} ·{" "}
                    {event.src_ip || "ไม่ระบุ IP"}
                  </p>
                  <h3>Request</h3>
                  <pre>{JSON.stringify(event.request, null, 2)}</pre>
                  <h3>Response</h3>
                  <pre>{JSON.stringify(event.response, null, 2)}</pre>
                  <h3>Log</h3>
                  <pre>{JSON.stringify(event.log, null, 2)}</pre>
                  <p className="run-muted">
                    ตรวจ status และ event_type ก่อนสรุปผล
                    การถูกบล็อกไม่ใช่หลักฐานว่าถูกเจาะสำเร็จ
                  </p>
                </>
              )}
            </section>
          </div>
          <div className="evidence-layout">
            <section className="run-panel" aria-labelledby="alerts-title">
              <h2 id="alerts-title">สัญญาณตรวจพบ</h2>
              {alerts.length === 0 ? (
                <p>ยังไม่มี alert จาก rule หรือ anomaly</p>
              ) : (
                <ol className="run-list">
                  {alerts.map((item) => (
                    <li key={item.id}>
                      <p>
                        <strong>
                          {item.detector_type === "anomaly"
                            ? "Anomaly"
                            : "Rule"}{" "}
                          · {item.severity}
                        </strong>{" "}
                        · {item.detector_version}
                      </p>
                      <p>{item.explanation}</p>
                      <p>
                        หลักฐาน {item.evidence_ids.length} รายการ ·{" "}
                        {item.ticket_id ? (
                          <Link
                            href={`/runs/${runId}/tickets/${item.ticket_id}`}
                          >
                            เปิด ticket
                          </Link>
                        ) : (
                          "ยังไม่มี ticket"
                        )}
                      </p>
                    </li>
                  ))}
                </ol>
              )}
            </section>
            <section className="run-panel" aria-labelledby="tickets-title">
              <h2 id="tickets-title">Ticket และคำวิเคราะห์</h2>
              <p>
                <Link href={`/runs/${runId}/tickets/new`}>
                  สร้าง ticket จากหลักฐาน
                </Link>
              </p>
              {tickets.length === 0 ? (
                <p>ยังไม่มี ticket</p>
              ) : (
                <ol className="run-list">
                  {tickets.map((item) => (
                    <li key={item.id}>
                      <Link href={`/runs/${runId}/tickets/${item.id}`}>
                        {item.title} · {item.severity} · {item.status}
                      </Link>
                    </li>
                  ))}
                </ol>
              )}
              <h3>AI-assisted analysis</h3>
              <p className="run-muted">
                ผล AI ไม่ใช่คะแนน · mode แสดงตามแต่ละรายการ ·
                ถามและดูคู่มืออ้างอิงในหน้า ticket
              </p>
              {analyses.length === 0 ? (
                <p>ยังไม่มีคำวิเคราะห์</p>
              ) : (
                <ol className="run-list">
                  {analyses.map((item) => (
                    <li key={item.id}>
                      <strong>{item.status}</strong> · mode={item.mode}
                      {item.result && (
                        <p>
                          {"summary" in item.result
                            ? item.result.summary
                            : item.result.answer}
                        </p>
                      )}
                      {item.error_code && (
                        <p role="status">{item.error_code}</p>
                      )}
                      {[
                        "failed",
                        "timed_out",
                        "invalid_output",
                        "quota_exceeded",
                      ].includes(item.status) && (
                        <button
                          disabled={
                            busy ||
                            !run ||
                            !["running", "paused", "reviewing"].includes(
                              run.status,
                            )
                          }
                          onClick={() => void retryAnalysis(item)}
                        >
                          ลองวิเคราะห์ซ้ำ
                        </button>
                      )}
                    </li>
                  ))}
                </ol>
              )}
            </section>
          </div>
        </>
      )}
    </main>
  );
}
