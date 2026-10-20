# ผลตรวจข้อ 16 — blind exam และ immutable submission

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


ตรวจ working tree บน branch `implementation-checklist` วันที่ 20 ตุลาคม 2026. ข้อนี้ยัง **ไม่ผ่านตรวจรับ**; checklist จึงยังไม่ติ๊ก

## สิ่งที่เพิ่ม

- Migration `0019_learning_path` และ `0020_exam_attempts` เพิ่ม lesson/progress, run mode, exam bank, private truth, attempt, frozen answer, grading revision และ level unlock; migration graph ตรวจพบ head `0020_exam_attempts` ต่อจาก `0019_learning_path`.
- Operator seed รวม training scenario, lesson และ exam bank ให้ Compose เรียกหลัง migration; exam truth อยู่ใน privileged seed image เท่านั้น. Runner ได้เฉพาะ sanitized event fixtures; API/frontend ไม่บรรจุ fixture assets.
- Exam fixtures สามกรณีใช้ชื่อ public แบบเดียวกันและไม่ใส่ label/expected result ใน learner projection.
- API เลือก case ฝั่ง server, ตรวจ lesson completion/version, active attempt, quota/cooldown, idempotency และ evidence ที่อยู่ใน released events ของ run เดียวกัน; submit freeze answer/cutoff และปิด run ใน transaction เดียว.
- Learner UI แสดงข้อสอบ, evidence, answer form, pending review และกู้ active attempt หลัง refresh ผ่าน API; ไม่มี authoritative data ใน browser storage.
- Learner UI กู้ผล finalized ล่าสุดหลัง refresh และเปิดทางเริ่ม attempt ใหม่เมื่อผลเป็น `failed|expired`; API latest-result จำกัดข้อมูลตามเจ้าของและไม่ส่งเฉลย.

## ผลตรวจ local

ผลตรวจล่าสุด 21 ต.ค. 2026: disposable Compose ผ่าน migration/seed/health checks; integration suite **81 passed / 81 deselected**, smoke **3 passed**, browser E2E **26 passed / 1 skipped**. Integration ยืนยัน start/idempotency, blind projection, submit/replay, owner isolation, lesson gate, concurrent Instructor review, unlock เมื่อผ่านครบทุก case, revision/audit, override ที่ไม่ถอน unlock, case cap และการแข่งเริ่ม retake หลัง attempt ก่อนหน้าตกและ cooldown หมด (มี active attempt ได้เพียงหนึ่งเดียว). Browser E2E ครอบคลุมเริ่มข้อสอบ ส่งคำตอบ `needs_review`, Instructor review จริงใน disposable DB, learner feedback หลัง refresh และการปฏิเสธ retry ระหว่าง cooldown. Retake policy กำหนด 3 attempts/case/24h (สูงสุด 9/level), case rotation/cap และ cooldown 1h หลัง fail. API ล่าสุด-result จำกัด ownership ผ่าน integration.

- Ruff lint/format ของไฟล์ backend ที่แก้, mypy และ `pytest -m 'not integration'`: ผ่าน; **93 passed** (deselected count แปรตาม integration tests ที่เพิ่ม; ล่าสุด 80).
- เพิ่ม `test_exam_integration.py` ครอบคลุม start/idempotency, frozen submit/replay, owner isolation และ assignment-scoped review; Compose integration suite ผ่านจริงบน PostgreSQL.
- OpenAPI YAML validation และ generated client check: ผ่าน. Exam routes ยังซ่อนจาก OpenAPI เพราะ contract เป็น draft.
- Frontend typecheck/lint/build ผ่าน; browser asset leakage test และ production landing smoke ผ่านอย่างละ 1 test.
- `git diff --check` ผ่าน.

## ยังต้องยืนยัน

ยังไม่มี browser E2E ที่เดินเวลาจน cooldown หมดแล้วเริ่ม attempt จริง; การเริ่ม retake หลัง cooldown และ race ตรวจใน PostgreSQL integration ส่วน browser ยืนยัน cooldown UX ผ่าน API จริงใน Compose. Compose integration และ browser flow ไม่ใช่ staging/deployment acceptance; เรียก Alembic ผ่าน migration wrapper ตาม harness.

## เพิ่มเติม 20 ต.ค. 2026

เพิ่ม `frontend/tests/browser/exam-review.spec.ts` สำหรับ UI contract ด้วย fixture และต่อยอด `frontend/tests/browser/learning.spec.ts` ให้ใน disposable Compose ทำ browser journey จริง: Analyst สมัคร/เรียน/ส่งข้อสอบ → operator provisions Instructor ชั่วคราวและ assign เฉพาะ Analyst → Instructor login/ตรวจคำตอบผ่าน UI/API → Analyst refresh แล้วเห็นผลและ feedback จาก PostgreSQL. รหัสผ่านสุ่มเฉพาะ run อยู่ในไฟล์ชั่วคราวและฐาน/volume ถูกลบโดย harness. วันที่ 20 ต.ค. 2026 `scripts/ci-compose.sh` ผ่าน: backend/PostgreSQL integration **81 passed**, smoke **3 passed**, browser **23 passed / 1 skipped**. GitHub CI ทุก job ผ่านบน commit `75ae111870c1c4da1ae152b0d16519ad723d5901` (run [39411788826](https://github.com/IMLV1/SOC/actions/runs/39411788826)). รอบก่อนหน้าล้มเพราะ container ใช้ UID `soc` ซึ่งอ่านไฟล์รหัสผ่านชั่วคราวที่สร้างเป็น mode `0600` โดย CI runner ไม่ได้; `scripts/ci-compose.sh` กำหนด UID/GID ให้ตรงเจ้าของไฟล์ก่อน provision. Docker CLI บนเครื่องนี้เรียกผ่าน `PATH="$PATH:/Applications/Docker.app/Contents/Resources/bin"`.

## ตรวจซ้ำ 21 ต.ค. 2026

บน checkout ปัจจุบัน (branch `codex/magic-ui-redesign`) `scripts/ci-compose.sh` ผ่าน migration/health, PostgreSQL integration **81 passed**, HTTP smoke **3 passed**, worker/evaluator readiness และ browser E2E **26 passed / 1 skipped**. เพิ่มการยืนยันว่า concurrent retry เกิดหลัง attempt ก่อนหน้าถูกปิดเป็น `failed` และ cooldown ถูกเลื่อนพ้นแล้วจริง; browser test ครอบคลุม response `EXAM_COOLDOWN_ACTIVE` และคงผลสอบตกไว้เมื่อ retry ถูกปฏิเสธ. Ruff check/format สำหรับ test backend, frontend lint/typecheck และ `git diff --check` ผ่าน. GitHub CI บน changes ล่าสุดยังรอยืนยัน; ไม่มี staging/deployment acceptance.
