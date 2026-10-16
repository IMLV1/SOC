"use client";
import { useEffect, useState } from "react";
import { read } from "../../lib/api";
import type { DemoEvent } from "../../lib/api-types";
export default function Demo() {
  const [events, setEvents] = useState<DemoEvent[] | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    read<DemoEvent[]>("/demo/events")
      .then((data) => {
        if (active) setEvents(data);
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
    };
  }, []);
  return (
    <main>
      <h1>อ่านหลักฐานตัวอย่าง</h1>
      <p className="notice">
        ข้อมูลจำลองแบบอ่านอย่างเดียว แยกจากรอบฝึกและข้อสอบ
        ไม่มีผลต่อคะแนนหรือบัญชี
      </p>
      {error ? (
        <p role="alert">โหลดข้อมูลไม่สำเร็จ กรุณารีเฟรชเพื่อลองใหม่</p>
      ) : events === null ? (
        <p role="status">กำลังโหลด…</p>
      ) : events.length === 0 ? (
        <p>ยังไม่มีข้อมูลตัวอย่าง</p>
      ) : (
        <div className="demo-events">
          {events.map((event) => (
            <article key={event.id}>
              <h2>
                {event.method} {event.path}
              </h2>
              <p>Response: {event.status_code}</p>
              <p>{event.description}</p>
              <time>{event.event_time}</time>
            </article>
          ))}
        </div>
      )}
    </main>
  );
}
