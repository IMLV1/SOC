"use client";
import { useEffect, useRef, useState } from "react";
import { ApiError, read, write } from "../lib/api";
import type { AnalysisView, SourceView, TicketView } from "../lib/api-types";

export function Assistant({
  runId,
  ticket,
  mutable,
}: {
  runId: string;
  ticket: TicketView;
  mutable: boolean;
}) {
  const [question, setQuestion] = useState("");
  const [items, setItems] = useState<AnalysisView[]>([]);
  const [source, setSource] = useState<SourceView | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const sourceAnalysis = useRef<string | null>(null);
  const sourceRequest = useRef(0);
  const admission = useRef<{ body: string; key: string } | null>(null);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    let delay = 1500;
    async function poll() {
      if (document.hidden) {
        timer = setTimeout(() => void poll(), 10000);
        return;
      }
      try {
        const data = await read<AnalysisView[]>(
          `/runs/${runId}/analyses?ticket_id=${ticket.id}`,
        );
        if (active) {
          setItems(data);
          if (
            data.some(
              (item) =>
                item.id === sourceAnalysis.current &&
                item.response_visibility === "withdrawn",
            )
          ) {
            ++sourceRequest.current;
            setSource(null);
          }
          delay = 1500;
        }
      } catch (error) {
        if (active)
          setMessage(
            error instanceof ApiError && error.status === 401
              ? "เซสชันหมดอายุ"
              : "โหลด AI ไม่สำเร็จ",
          );
        delay = Math.min(delay * 2, 15000);
      } finally {
        if (active) timer = setTimeout(() => void poll(), delay);
      }
    }
    void poll();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [runId, ticket.id]);
  function failure(error: unknown) {
    if (error instanceof ApiError) {
      if (error.status === 401) return "เซสชันหมดอายุ กรุณาเข้าสู่ระบบ";
      if (error.status === 409)
        return "ข้อมูลเปลี่ยนหรือแหล่งถูกถอน ร่างคำถามยังอยู่";
      if (error.status === 429) return "โควตา AI ไม่พอ";
      if (error.code === "DIFY_QUESTION_REQUIRES_REAL_RUN")
        return "รอบนี้ใช้ AI จำลอง หากต้องการถาม Dify ให้เริ่มรอบใหม่ที่เปิด AI จริง ประวัติรอบเดิมยังอยู่";
      if (error.code === "DIFY_ANALYSIS_NOT_APPROVED")
        return "Dify หรือคู่มือของรอบนี้ไม่พร้อม หรือเปลี่ยนเวอร์ชันแล้ว ร่างคำถามยังอยู่";
      if (error.status === 503)
        return "Knowledge/provider ยังไม่พร้อมสำหรับรอบนี้";
      if (error.status === 410) return "แหล่งถูกถอนแล้ว (withdrawn)";
    }
    return "AI ไม่พร้อม การสืบสวนและบันทึกยังทำต่อได้";
  }
  async function ask() {
    setBusy(true);
    setMessage("");
    try {
      const body = JSON.stringify({
        question,
        expected_version: ticket.version,
      });
      if (admission.current?.body !== body)
        admission.current = { body, key: crypto.randomUUID() };
      const item = await write<AnalysisView>(
        `/runs/${runId}/tickets/${ticket.id}/questions`,
        { question, expected_version: ticket.version },
        { idempotencyKey: admission.current.key },
      );
      admission.current = null;
      setItems((current) => [item, ...current]);
      setQuestion("");
    } catch (error) {
      setMessage(failure(error));
    } finally {
      setBusy(false);
    }
  }
  async function retry(item: AnalysisView) {
    setBusy(true);
    try {
      const next = await write<AnalysisView>(
        `/runs/${runId}/analyses/${item.id}/retry`,
        { expected_version: item.version },
        { idempotencyKey: crypto.randomUUID() },
      );
      setItems((current) => [next, ...current]);
    } catch (error) {
      setMessage(failure(error));
    } finally {
      setBusy(false);
    }
  }
  async function openSource(item: AnalysisView, id: string) {
    setSource(null);
    sourceAnalysis.current = item.id;
    const current = ++sourceRequest.current;
    try {
      const data = await read<SourceView>(
        `/runs/${runId}/analyses/${item.id}/sources/${id}`,
      );
      if (current === sourceRequest.current) setSource(data);
    } catch (error) {
      if (current === sourceRequest.current) setMessage(failure(error));
    }
  }
  return (
    <section className="run-panel" style={{ overflowWrap: "anywhere" }}>
      <h2>Ask AI / Triage</h2>
      <p>
        ถามเกี่ยวกับหลักฐานใน ticket นี้ เช่น “หลักฐานยังขาดอะไร?” หรือ
        “ควรตรวจ log อะไรเพิ่ม?” AI ช่วยตีความ ไม่ใช่หลักฐานยืนยันผลกระทบหรือคะแนน
        รอบที่ใช้ AI จริงต้องมี Dify และคู่มือเวอร์ชันที่อนุมัติไว้พร้อมใช้งาน
      </p>
      <label>
        คำถามเกี่ยวกับ ticket
        <textarea
          value={question}
          maxLength={2000}
          disabled={!mutable || !!ticket.deleted_at}
          onChange={(event) => setQuestion(event.target.value)}
        />
      </label>
      <button
        disabled={!mutable || !!ticket.deleted_at || busy || !question.trim()}
        onClick={() => void ask()}
      >
        ถาม AI
      </button>
      {!mutable && <p>รอบอ่านอย่างเดียว ไม่เปิด Ask AI</p>}
      {message && <p role="alert">{message}</p>}
      {items.length === 0 && <p>ยังไม่มีคำวิเคราะห์</p>}
      {items.map((item) => (
        <article key={item.id}>
          <h3>
            {item.kind} · mode={item.mode} · {item.status}
          </h3>
          {item.question_text && <p>{item.question_text}</p>}
          <p>
            {item.retrieval
              ? `retrieval=${item.retrieval.status}`
              : item.mode === "real"
                ? "คู่มือผ่าน Dify · ตรวจแหล่งอ้างอิงก่อนแสดงผล"
                : "ผลจำลอง · ไม่ได้ค้นคู่มือ"} ·{" "}
            {item.response_visibility}
          </p>
          {item.response_visibility === "withdrawn" ? (
            <p>คำตอบถูกถอนแล้ว</p>
          ) : (
            item.result && (
              <>
                <p>
                  {"answer" in item.result
                    ? item.result.answer
                    : item.result.summary}
                </p>
                {"answer_status" in item.result && (
                  <p>{item.result.answer_status}</p>
                )}
                <details>
                  <summary>ผลแบบ structured และหลักฐานเหตุการณ์</summary>
                  <pre
                    style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}
                  >
                    {JSON.stringify(item.result, null, 2)}
                  </pre>
                </details>
              </>
            )
          )}
          {item.error_code && <p>{item.error_code}</p>}
          <p>คู่มืออ้างอิง</p>
          {item.retrieval?.citations.map((citation) => (
            <button
              key={citation.retrieval_item_id}
              onClick={() => void openSource(item, citation.retrieval_item_id)}
            >
              {citation.document_title} · {citation.document_version}
            </button>
          ))}
          {["failed", "timed_out", "invalid_output", "quota_exceeded"].includes(
            item.status,
          ) && (
            <button
              disabled={
                !mutable ||
                !!ticket.deleted_at ||
                busy ||
                item.response_visibility === "withdrawn"
              }
              onClick={() => void retry(item)}
            >
              ลอง AI ใหม่ด้วย snapshot เดิม
            </button>
          )}
        </article>
      ))}
      {source && (
        <aside
          role="dialog"
          aria-modal="false"
          aria-label="แหล่งอ้างอิง"
          tabIndex={-1}
        >
          <button
            onClick={() => {
              ++sourceRequest.current;
              sourceAnalysis.current = null;
              setSource(null);
            }}
          >
            ปิดแหล่งอ้างอิง
          </button>
          <h3>
            {source.document_title} · {source.document_version}
          </h3>
          <p>{source.heading}</p>
          <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
            {source.excerpt}
          </pre>
          <p>{source.content_hash}</p>
        </aside>
      )}
    </section>
  );
}
