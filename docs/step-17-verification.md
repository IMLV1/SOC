# ผลตรวจข้อ 17 — grading, feedback, review และ unlock

ตรวจ working tree บน branch `implementation-checklist` วันที่ 18 ตุลาคม 2026. ข้อนี้ยัง **ไม่ผ่านตรวจรับ**; checklist จึงยังไม่ติ๊ก

อัปเดต local evidence 18 ต.ค. 2026: Compose migration/health checks ผ่าน; integration **80 passed / 81 deselected**, smoke **3 passed**, browser E2E **22 passed / 1 skipped**; worker/evaluator readiness ผ่าน. Integration ยืนยัน concurrent review ให้ผู้ชนะหนึ่งคำขอ, ปลดล็อกหลังผ่านครบสาม case, append override revision/audit และไม่ถอน unlock เดิม. Browser E2E ยังไม่มี flow feedback/Instructor review.

## Policy และ implementation

ค่าเริ่มต้น D-01–D-04 ที่ผู้ใช้มอบหมายอยู่ใน [SRS §8](srs.md#8-decision-register--ข้อสรุปที่ผู้ใช้มอบหมายให้กำหนด-และเรื่องที่ยังค้าง): rubric `soc-foundations-v1` 4 criteria, 0–2 คะแนนต่อเกณฑ์, ผ่านเมื่อได้อย่างน้อย 6/8 และ critical criteria `evidence`/`analysis` ต้องได้อย่างน้อย 1. Evidence ต้องอ้าง released events ใน run เดียวกัน. Missing/invalid/ambiguous input ต้องไม่ auto-pass. จำกัด 3 attempts ต่อ level ต่อ rolling 24 ชั่วโมง, cooldown 1 ชั่วโมงหลัง fail, attempt หมดอายุ 24 ชั่วโมง; override append revision/audit แต่ไม่ถอน unlock ที่ได้แล้ว.

เพิ่ม deterministic rubric, frozen answer, grading revisions, assignment-scoped Instructor truth access หลัง submit, audit ของการอ่าน truth, human review, feedback projection และ level unlock ที่สร้างครั้งเดียว. เพิ่มคิว Instructor และหน้าอ่านคำตอบ/เฉลย/ให้คะแนน. **Real AI/provider grading ยังไม่เปิด** ตามขอบเขตที่ผู้ใช้กำหนด; ไม่มีค่าใช้จ่าย/provider call.

## ผลตรวจ local

- Ruff lint/format ของไฟล์ backend ที่แก้, mypy และ `pytest -m 'not integration'`: ผ่าน; **93 passed** (deselected count แปรตาม integration tests ที่เพิ่ม; ล่าสุด 80).
- เพิ่ม integration coverage สำหรับ assignment-scoped truth/review; Compose integration suite ผ่านจริงบน PostgreSQL.
- Frontend typecheck/lint/build ผ่าน; browser asset leakage test และ production landing smoke ผ่านอย่างละ 1 test.
- Migration graph ชี้ `0020_exam_attempts` เป็น head; `git diff --check` ผ่าน.

## ยังต้องยืนยัน

ณ รายงานเดิมยังขาด browser E2E ของ learner feedback กับ Instructor review; มีหลักฐานเพิ่มในวันที่ 20 ต.ค. 2026 ด้านล่าง. Integration race/override/unlock coverage ฝั่ง PostgreSQL ยังไม่ครอบคลุมทุก interleaving. AI grading จริงและ citations ยังไม่เปิดตาม scope ที่ผู้ใช้ระบุ.

## เพิ่มเติม 20 ต.ค. 2026

เพิ่ม browser UI regression ใน `frontend/tests/browser/exam-review.spec.ts` และ full-stack browser journey ใน `frontend/tests/browser/learning.spec.ts`: Instructor จริงใน disposable DB ตรวจคำตอบของ Analyst ที่ assigned ผ่านหน้าเว็บ/API และ Analyst เห็นผล/feedback หลัง refresh. วันที่ 20 ต.ค. 2026 local disposable Compose ผ่าน integration 81 tests, smoke 3 tests, browser 23 passed/1 skipped; PostgreSQL integration ครอบคลุม assignment, concurrent review, unlock และ override. ยังรอ GitHub CI บน changes ล่าสุดและ coverage interleavings เพิ่มเติม; Step 17 ยังขึ้นกับการตรวจรับ Step 14 ตามลำดับ checklist จึงยังไม่ติ๊ก.
