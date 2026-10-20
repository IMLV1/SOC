# ผลตรวจข้อ 11 — Evaluation, completion และ Instructor

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


ตรวจวันที่ 15 ตุลาคม 2026 บน branch `codex/step-05-scenarios` โดยเก็บงาน local เดิมไว้ทั้งหมด

การตรวจรับ local ผ่าน:

- PostgreSQL 17.11 disposable integration ผ่าน full `scripts/ci-compose.sh`: **50 passed, 30 deselected**. ครอบคลุม finish/cutoff, late analysis fencing, immutable snapshot, role grants, assignment/ownership, read-only completion, Instructor comment และ JSON export
- Chromium E2E: **11 passed** รวม flow ใหม่ login → start training → finish → evaluation snapshot → ดาวน์โหลด JSON; browser ใช้ mock provider
- Frontend HTTP smoke: **3 passed** บน Compose local stack
- Metrics/experiment tests และ OpenAPI validate/approved-contract drift: **5 passed**; A/B เรียก detector implementation จริงบน input เดียวกัน ส่วน C เป็น `unavailable`
- Generated client types `--check` ผ่าน
- Ruff, mypy, ESLint และ Next.js typecheck ผ่าน

Implementation เพิ่ม migration `0010_evaluation_and_experiments`, ตาราง snapshot ที่ DB ป้องกันการแก้ย้อนหลัง, `evaluator_runtime` แยกจาก API/worker และ evaluator service ใน Compose. `finish` ทำ cutoffs ขณะ lock run ก่อน job, evaluator drain งาน detection/analysis ไม่เกิน 60 วินาที และยกเลิก/fence output ที่มาหลัง deadline. JSON export ไม่รวม private truth.

Ground truth version ถูก pin ตอนสร้าง training run. เจ้าของอ่าน training truth ได้หลัง completion; Instructor อ่าน truth ของ run ที่ได้รับ assignment ได้ระหว่าง training และหลัง evaluation พร้อม audit. Exam routes ยังไม่เปิด. Run หลัง finish เป็น read-only; Instructor comments เป็น resource แยกและไม่มี endpoint เขียน assessment/note.

Detector metrics ใช้ detection evidence โดยไม่ให้ manual ticket หรือ soft delete เปลี่ยน denominator; zero-denominator metrics คืน `null` พร้อม reason. Human metrics คง `unavailable: HUMAN_SCORING_POLICY_UNDECIDED`; ยังไม่มี learner score จนกว่าจะอนุมัติ rubric/scoring policy. Instructor account, quota และ assignment สร้างผ่าน operator CLI; ยังไม่มี public admin user/quota API.

ข้อจำกัดที่ยังค้าง: GitHub CI ของ changeset นี้ยังไม่ได้รัน; C ยัง unavailable จนมี global provider/budget controls ที่ผ่านข้อ 12; rubric, retake และ override/revoke unlock ยัง pending. การทดสอบ local แสดง warning ที่ไม่ทำให้ fail: Starlette/httpx deprecation และ pytest cache permission ใน container.
