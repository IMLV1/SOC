"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, read, readPage, write } from "../../lib/api";
import type { ScenarioView } from "../../lib/api-types";
import type { Run } from "../../lib/run-types";
import { useSession } from "../session-provider";

export default function RunsPage() {
  const { session } = useSession();
  return <RunsWorkspace key={session ? `${session.user.id}:${session.user.role}:${session.user.status}` : "guest"} />;
}

function RunsWorkspace() {
  const router = useRouter();
  const { session, loading: sessionLoading, preview } = useSession();
  const userId = session?.user.id;
  const mounted = useRef(false);
  const generation = useRef(0);
  const [cursor, setCursor] = useState<string | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioView[]>([]);
  const [selected, setSelected] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [startError, setStartError] = useState("");
  const [startErrorCode, setStartErrorCode] = useState("");
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  const load = useCallback(async () => {
    if (!userId) return;
    const request = ++generation.current;
    const current = () => mounted.current && request === generation.current;
    setRefreshing(true);
    try {
      const [page, catalog] = await Promise.all([
        readPage<Run[]>("/runs"),
        read<ScenarioView[]>("/scenarios"),
      ]);
      if (!current()) return;
      const items = page.data;
      setCursor(page.meta.next_cursor ?? null);
      setRuns(items);
      setScenarios(catalog);
      setSelected(
        (current) =>
          (catalog.some((item) => item.id === current) ? current : "") ||
          catalog.find((item) => item.title.includes("S02"))?.id ||
          catalog[0]?.id ||
          "",
      );
      setMessage("");
    } catch (error) {
      if (!current()) return;
      setMessage(
        error instanceof ApiError && error.status === 401
          ? "เซสชันหมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง"
          : "โหลดรอบฝึกไม่สำเร็จ",
      );
    } finally {
      if (current()) { setLoading(false); setRefreshing(false); }
    }
  }, [userId]);
  useEffect(() => {
    if (!userId) return;
    const timer = setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
  }, [userId, load]);
  async function more() {
    if (!cursor || busy || refreshing) return;
    const request = generation.current;
    const current = () => mounted.current && request === generation.current;
    setBusy(true);
    try {
      const page = await readPage<Run[]>(
        `/runs?cursor=${encodeURIComponent(cursor)}`,
      );
      if (!current()) return;
      setRuns((current) => [
        ...current,
        ...page.data.filter(
          (item) => !current.some((old) => old.id === item.id),
        ),
      ]);
      setCursor(page.meta.next_cursor ?? null);
    } catch (error) {
      if (!current()) return;
      setMessage(
        error instanceof ApiError && error.status === 401
          ? "เซสชันหมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง"
          : "โหลดหน้าถัดไปไม่สำเร็จ",
      );
    } finally {
      if (current()) setBusy(false);
    }
  }
  async function start() {
    if (!selected || preview || busy || loading || refreshing) return;
    setBusy(true);
    setStartError("");
    setStartErrorCode("");
    try {
      const run = await write<Run>(
        "/runs",
        { scenario_ids: [selected] },
        { idempotencyKey: crypto.randomUUID() },
      );
      if (mounted.current) router.push(`/runs/${run.id}`);
    } catch (error) {
      if (!mounted.current) return;
      const code = error instanceof ApiError ? error.code : "";
      setStartErrorCode(code);
      setStartError(
        code === "RUN_ALREADY_RUNNING"
          ? "มีรอบฝึกหรือข้อสอบที่กำลังทำอยู่ ให้เปิดรอบเดิมจากประวัติด้านล่าง หรือตรวจสถานะข้อสอบก่อนเริ่มรอบใหม่"
          : code === "IDEMPOTENCY_CONFLICT"
            ? "คำขอซ้ำไม่ตรงกับคำขอเดิม กรุณาโหลดรายการล่าสุดก่อนลองเริ่มใหม่"
            : error instanceof ApiError && error.status === 401
              ? "เซสชันหมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง"
              : error instanceof ApiError && error.status === 429
                ? "โควตารอบฝึกวันนี้หมดแล้ว"
                : error instanceof ApiError && error.status === 503
                  ? "ระบบเริ่มรอบฝึกยังไม่พร้อม กรุณาลองใหม่ภายหลัง หรือไปหน้าฝึกอ่านหลักฐาน"
                  : "เริ่มรอบฝึกไม่สำเร็จ กรุณาลองใหม่ หากยังไม่ได้ ให้ตรวจสถานะ API และ runner",
      );
      // Reload domain state without erasing the failure that explains this action.
      void load();
    } finally {
      if (mounted.current) setBusy(false);
    }
  }
  return (
    <main className="run-shell">
      <div className="run-topline">
        <span>Sentinel / Training</span>
        <span>01 — Runs</span>
      </div>
      <h1>รอบฝึกของฉัน</h1>
      <p className="run-lead">
        เลือกสถานการณ์ แล้วติดตามหลักฐานที่ระบบปล่อยตามเวลาจริง
        รอบฝึกยังไม่ใช่ข้อสอบเลื่อนระดับ
      </p>
      <p><Link href="/practice">ฝึกอ่านหลักฐานรวมพร้อมบันทึกคำตอบ</Link> — แบบฝึกจากฐานข้อมูลแยกจากรอบ simulation และข้อสอบ</p>
      {sessionLoading ? (
        <p role="status">กำลังตรวจบัญชี…</p>
      ) : !session ? (
        <p>
          <Link href="/login">เข้าสู่ระบบเพื่อเริ่มรอบฝึก</Link>
        </p>
      ) : (
        <>
          <section className="run-panel" aria-labelledby="start-title">
            <h2 id="start-title">เริ่มรอบใหม่</h2>
            <label>
              สถานการณ์
              <select
                value={selected}
                onChange={(event) => setSelected(event.target.value)}
                disabled={busy || loading || refreshing}
              >
                {scenarios.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.title} · {item.duration_ms / 1000} วินาที
                  </option>
                ))}
              </select>
            </label>
            <button
              onClick={() => void start()}
              disabled={preview || busy || loading || refreshing || !selected}
            >
              {preview
                ? "Runner ยังไม่พร้อมบน preview"
                : busy
                  ? "กำลังเริ่ม…"
                  : loading
                    ? "กำลังโหลดสถานการณ์…"
                    : !selected
                      ? "ยังไม่มีสถานการณ์ให้เริ่ม"
                      : "เริ่มรอบฝึก"}
            </button>
            <p className="run-muted">
              รอบนี้ใช้ API/ฐานข้อมูลและ runner จริง เริ่มได้เมื่อไม่มีรอบที่กำลังทำหรือข้อสอบค้างอยู่ · log มาจาก fixture ที่เตรียมไว้ โหมด AI แสดงในแต่ละรอบ: mock คือผลจำลอง ส่วน real ใช้ Dify คำแนะนำ AI ไม่ใช่คะแนน
            </p>
          </section>
          {(startError || message) && (
            <p role="alert" className="run-alert">
              {startError || message}{" "}
              {startErrorCode === "RUN_ALREADY_RUNNING" && <><Link href="/learning">ตรวจสถานะข้อสอบ</Link>{" "}</>}
              {startError && <Link href="/login">ตรวจการเข้าสู่ระบบ</Link>}{" "}
              <button
                disabled={busy || refreshing}
                onClick={() => void load()}
              >
                โหลดรายการใหม่
              </button>
            </p>
          )}
          <section className="run-panel" aria-labelledby="list-title" aria-busy={refreshing}>
            <div className="run-section-head">
              <h2 id="list-title">ประวัติรอบฝึก</h2>
              <button disabled={busy || refreshing} onClick={() => void load()}>รีเฟรช</button>
            </div>
            {refreshing && !loading && <p role="status">กำลังอัปเดตรายการ…</p>}
            {loading ? (
              <p role="status">กำลังโหลด…</p>
            ) : runs.length === 0 ? (
              <p>ยังไม่มีรอบฝึก</p>
            ) : (
              <ol className="run-list">
                {runs.map((item) => (
                  <li key={item.id}>
                    <Link href={`/runs/${item.id}`}>
                      <span className="run-status">{item.status}</span>
                      <span>
                        {new Date(item.server_time).toLocaleString("th-TH")}
                      </span>
                      <span>
                        ความคืบหน้า{" "}
                        {Math.round((item.elapsed_ms / item.duration_ms) * 100)}
                        %
                      </span>
                    </Link>
                  </li>
                ))}
              </ol>
            )}
            {cursor && (
              <button disabled={busy || refreshing} onClick={() => void more()}>
                โหลดรอบเพิ่มเติม
              </button>
            )}
          </section>
        </>
      )}
    </main>
  );
}
