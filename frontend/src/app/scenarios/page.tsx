"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { read } from "../../lib/api";
import type { ScenarioView } from "../../lib/api-types";

export default function ScenariosPage() {
  const [items, setItems] = useState<ScenarioView[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    read<ScenarioView[]>("/scenarios")
      .then((data) => {
        if (active) setItems(data);
      })
      .catch(() => {
        if (active) setError(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [retry]);
  return (
    <main className="account-page">
      <p className="eyebrow">TRAINING CATALOG</p>
      <h1>สถานการณ์ฝึก</h1>
      <p>
        ดูหัวข้อและเป้าหมายการฝึกได้โดยไม่ต้องเข้าสู่ระบบ
        เข้าสู่ระบบเพื่อเริ่มรอบฝึก รายการนี้ไม่ใช่ข้อสอบเลื่อนระดับ;
        หากต้องการสอบให้เริ่มที่บทเรียนพื้นฐานก่อน
      </p>
      {loading ? (
        <p role="status">กำลังโหลดสถานการณ์…</p>
      ) : error ? (
        <p role="alert">
          โหลดสถานการณ์ไม่สำเร็จ{" "}
          <button
            onClick={() => {
              setLoading(true);
              setError(false);
              setRetry((value) => value + 1);
            }}
          >
            ลองใหม่
          </button>
        </p>
      ) : items.length === 0 ? (
        <p>ยังไม่มีสถานการณ์ที่เปิดให้ดู</p>
      ) : (
        <div className="scenario-list">
          {items.map((item) => (
            <article key={item.id}>
              <h2>{item.title}</h2>
              <p>
                เวอร์ชัน {item.version} ·{" "}
                {
                  {
                    beginner: "เริ่มต้น",
                    intermediate: "กลาง",
                    advanced: "ชำนาญ",
                  }[item.difficulty]
                }{" "}
                · {item.duration_ms / 1000} วินาที
              </p>
              <ul>
                {item.learning_objectives.map((objective) => (
                  <li key={objective}>{objective}</li>
                ))}
              </ul>
              <p>
                <Link href="/runs">ไปหน้ารอบฝึก</Link>
              </p>
            </article>
          ))}
        </div>
      )}
      <p><Link href="/learning">ไปเส้นทางบทเรียนและข้อสอบ</Link> · <Link href="/demo">ลองอ่าน request ก่อนสมัคร</Link></p>
    </main>
  );
}
