"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { read } from "../../lib/api";
import type { DemoEvent } from "../../lib/api-types";
import { useSession } from "../session-provider";

type Field = "method" | "path" | "status" | "time";

const steps: { field: Field; label: string; instruction: string }[] = [
  { field: "method", label: "Method", instruction: "กด Method เพื่อดูว่า client ขอให้ server ทำอะไร" },
  { field: "path", label: "Path", instruction: "กด Path เพื่อดูว่าคำขอนี้ไปที่หน้าไหน" },
  { field: "status", label: "Response status", instruction: "กด Response status เพื่อดูผลที่ server ตอบกลับ" },
  { field: "time", label: "Time", instruction: "กด Time เพื่อวางเหตุการณ์บน timeline" },
];

function explain(field: Field, event: DemoEvent): string {
  if (field === "method") return `${event.method} คือวิธีส่งคำขอ; GET มักใช้ขออ่านข้อมูล แต่บอกไม่ได้เองว่าเป็นการโจมตี`;
  if (field === "path") return `${event.path} คือปลายทางที่ถูกขอ; ต้องเทียบบริบทและสิทธิ์ก่อนตัดสินว่าผิดปกติ`;
  if (field === "status") return event.status_code === 200
    ? "200 หมายถึง server ตอบคำขอนี้สำเร็จ ไม่ได้แปลว่ามีการบุกรุกหรือข้อมูลรั่ว"
    : `${event.status_code} คือผลของคำขอนี้ ไม่ได้พิสูจน์ว่าทั้งเคสปลอดภัย ต้องดูเหตุการณ์อื่นประกอบ`;
  return "เวลาใช้เรียงลำดับกับ event อื่น; เวลาเพียงจุดเดียวไม่บอกเจตนาหรือผลกระทบ";
}

export default function Demo() {
  const { session } = useSession();
  const [events, setEvents] = useState<DemoEvent[] | null>(null);
  const [error, setError] = useState(false);
  const [eventIndex, setEventIndex] = useState(0);
  const [stepIndex, setStepIndex] = useState(0);
  const [selected, setSelected] = useState<Field | null>(null);
  useEffect(() => {
    let active = true;
    read<DemoEvent[]>("/demo/events")
      .then((data) => { if (active) setEvents(data); })
      .catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, []);

  const event = events?.[eventIndex];
  const expected = steps[stepIndex];
  const correct = selected === expected?.field;

  function chooseEvent(index: number) {
    setEventIndex(index);
    setStepIndex(0);
    setSelected(null);
  }

  return (
    <main className="account-page demo-page">
      <p className="eyebrow">ทดลองก่อนสมัคร / ไม่บันทึกคะแนน</p>
      <h1>ลองอ่าน request ด้วยตัวเอง</h1>
      <p>กดข้อมูลตามคำใบ้ทีละจุด แล้วดูว่าข้อมูลนั้นบอกอะไรได้และยังบอกอะไรไม่ได้</p>
      <p className="notice">นี่คือข้อมูลจำลองแบบอ่านอย่างเดียว ไม่มีการบันทึกความคืบหน้า ไม่ใช่ข้อสอบ และไม่เปลี่ยนข้อมูลในบัญชี</p>
      {error ? <p role="alert">โหลดข้อมูลไม่สำเร็จ กรุณารีเฟรชเพื่อลองใหม่</p>
        : events === null ? <p role="status">กำลังโหลด…</p>
          : events.length === 0 ? <p>ยังไม่มีข้อมูลตัวอย่าง</p>
            : <>
              <div className="demo-event-picker" aria-label="เลือกเหตุการณ์ตัวอย่าง">
                {events.map((item, index) => <button key={item.id} type="button" aria-pressed={index === eventIndex} onClick={() => chooseEvent(index)}>
                  ตัวอย่าง {index + 1}: {item.method} {item.path}
                </button>)}
              </div>
              {event && <div className="demo-playground">
                <section className="demo-instruction" aria-live="polite">
                  <p className="eyebrow">{expected ? `ขั้น ${stepIndex + 1} / ${steps.length}` : "อ่านครบแล้ว"}</p>
                  <h2>{expected ? expected.instruction : "ลองเชื่อมข้อมูลหลายจุด"}</h2>
                  {expected ? <>
                    <p>เลือกช่องด้านล่างให้ตรงกับคำใบ้ ปุ่มจะเปิดคำอธิบาย ไม่มีการหักคะแนน</p>
                    {selected && <p className={correct ? "demo-feedback demo-feedback--correct" : "demo-feedback"} role="status">
                      {correct ? explain(selected, event) : `ยังไม่ใช่ช่องนี้ ลองกด ${expected.label}`}
                    </p>}
                    <button type="button" disabled={!correct} onClick={() => { setStepIndex((current) => current + 1); setSelected(null); }}>ไปขั้นถัดไป</button>
                  </> : <>
                    <p>สอง request นี้ยังไม่พอจะสรุปว่ามีภัยคุกคาม ลองเทียบเวลา ผลตอบกลับ และหลักฐานอื่นก่อนตัดสิน</p>
                    <div className="demo-actions">
                      {events.length > 1 && <button type="button" onClick={() => chooseEvent((eventIndex + 1) % events.length)}>ลองตัวอย่างถัดไป</button>}
                      <Link className="button button-secondary" href={session ? "/learning" : "/register"}>{session ? "ไปบทเรียนที่บันทึกความคืบหน้า" : "สมัครเพื่อเริ่มบทเรียน"}</Link>
                    </div>
                  </>}
                </section>
                <article className="demo-request" aria-label="รายละเอียด request ตัวอย่าง">
                  <h2>{event.method} {event.path}</h2>
                  <p>{event.description}</p>
                  <div className="demo-fields">
                    <button type="button" onClick={() => setSelected("method")} aria-pressed={selected === "method"}><small>Method</small><strong>{event.method}</strong></button>
                    <button type="button" onClick={() => setSelected("path")} aria-pressed={selected === "path"}><small>Path</small><strong>{event.path}</strong></button>
                    <button type="button" onClick={() => setSelected("status")} aria-pressed={selected === "status"}><small>Response status</small><strong>{event.status_code}</strong></button>
                    <button type="button" onClick={() => setSelected("time")} aria-pressed={selected === "time"} aria-label={`Time (UTC) ${event.event_time}`}><small>Time (UTC)</small><strong>{event.event_time}</strong></button>
                  </div>
                  <p className="demo-caveat">ตัวอย่างนี้ไม่มี response body, บัญชีผู้ใช้ หรือ IP จึงยังตรวจผลกระทบไม่ได้</p>
                </article>
              </div>}
            </>}
    </main>
  );
}
