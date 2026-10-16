"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, read, readPage, write } from "../../lib/api";
import type { ScenarioView } from "../../lib/api-types";
import type { Run } from "../../lib/run-types";
import { useSession } from "../session-provider";

export default function RunsPage() {
  const router = useRouter();
  const { session, loading: sessionLoading, preview } = useSession();
  const [cursor, setCursor] = useState<string | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioView[]>([]);
  const [selected, setSelected] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const load = useCallback(async () => {
    try {
      const [page, catalog] = await Promise.all([
        readPage<Run[]>("/runs"),
        read<ScenarioView[]>("/scenarios"),
      ]);
      const items = page.data;
      setCursor(page.meta.next_cursor ?? null);
      setRuns(items);
      setScenarios(catalog);
      setSelected(
        (current) =>
          current ||
          catalog.find((item) => item.title.includes("S02"))?.id ||
          catalog[0]?.id ||
          "",
      );
      setMessage("");
    } catch (error) {
      setMessage(
        error instanceof ApiError && error.status === 401
          ? "เซสชันหมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง"
          : "โหลดรอบฝึกไม่สำเร็จ",
      );
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    if (!session) return;
    const timer = setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
  }, [session, load]);
  async function more() {
    if (!cursor || busy) return;
    setBusy(true);
    try {
      const page = await readPage<Run[]>(
        `/runs?cursor=${encodeURIComponent(cursor)}`,
      );
      setRuns((current) => [
        ...current,
        ...page.data.filter(
          (item) => !current.some((old) => old.id === item.id),
        ),
      ]);
      setCursor(page.meta.next_cursor ?? null);
    } catch (error) {
      setMessage(
        error instanceof ApiError && error.status === 401
          ? "เซสชันหมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง"
          : "โหลดหน้าถัดไปไม่สำเร็จ",
      );
    } finally {
      setBusy(false);
    }
  }
  async function start() {
    if (!selected || preview) return;
    setBusy(true);
    setMessage("");
    try {
      const run = await write<Run>(
        "/runs",
        { scenario_ids: [selected] },
        { idempotencyKey: crypto.randomUUID() },
      );
      router.push(`/runs/${run.id}`);
    } catch (error) {
      setMessage(
        error instanceof ApiError && error.status === 409
          ? "มีรอบที่กำลังทำอยู่ หรือคำขอซ้ำไม่ตรงกัน"
          : error instanceof ApiError && error.status === 429
            ? "โควตารอบฝึกวันนี้หมดแล้ว"
            : "เริ่มรอบฝึกไม่สำเร็จ",
      );
      void load();
    } finally {
      setBusy(false);
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
                disabled={busy || loading}
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
              disabled={preview || busy || !selected}
            >
              {preview
                ? "Runner ยังไม่พร้อมบน preview"
                : busy
                  ? "กำลังเริ่ม…"
                  : "เริ่มรอบฝึก"}
            </button>
            <p className="run-muted">
              เริ่มได้ครั้งละหนึ่งรอบที่กำลังทำอยู่ · โหมด AI mock
              ไม่ใช่ผลประเมินจริง
            </p>
          </section>
          {message && (
            <p role="alert" className="run-alert">
              {message}{" "}
              <button
                onClick={() => {
                  setLoading(true);
                  void load();
                }}
              >
                ลองใหม่
              </button>
            </p>
          )}
          <section className="run-panel" aria-labelledby="list-title">
            <div className="run-section-head">
              <h2 id="list-title">ประวัติรอบฝึก</h2>
              <button onClick={() => void load()}>รีเฟรช</button>
            </div>
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
              <button disabled={busy} onClick={() => void more()}>
                โหลดรอบเพิ่มเติม
              </button>
            )}
          </section>
        </>
      )}
    </main>
  );
}
