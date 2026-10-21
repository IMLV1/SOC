import { Suspense } from "react";
import CurriculumPreview from "./reader";

export const metadata = { title: "บทเรียนตัวอย่าง 3 ระดับ — Sentinel" };

export default function LearningPreviewPage() {
  return <Suspense fallback={<main className="account-page"><p role="status">กำลังเปิดเนื้อหาจากไฟล์…</p></main>}>
    <CurriculumPreview />
  </Suspense>;
}
