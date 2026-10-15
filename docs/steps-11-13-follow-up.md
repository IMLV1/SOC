# ข้อ 11–13 — งานค้างที่ต้องทำต่อ

อัปเดต 15 ตุลาคม 2026 หลังผู้ใช้ยืนยัน AI Studio project เป็น Free Tier แบบไม่มี billing
Gemini key ถูกเก็บใน `.local/secrets/gemini_api_key.txt`; ไม่พิมพ์/commit key
ข้อ 10 เชื่อม provider จริงแล้วเฉพาะ run ฝึก local และ synthetic events
Gemini 2.5 Flash ตอบ HTTP 404 ใน project ใหม่นี้; Google ระบุว่าจำกัด 2.5 สำหรับ project ที่เคยใช้
จึง pin Gemini 3.5 Flash-Lite ซึ่งเอกสารปัจจุบันระบุ stable, structured output และ Free Tier
real UI flow login → start S02 → worker analysis → pause/resume ผ่าน Chromium; analysis สำเร็จ
DB เก็บ mode/model/token usage และ quota reservation consumed; mock ยังคงค่าเริ่มต้น
worker รับ key ผ่าน Docker secret เฉพาะ service; test container ได้เฉพาะ DB test role secrets
Free Tier อาจนำเนื้อหาไปปรับปรุงผลิตภัณฑ์ ใช้เฉพาะ synthetic fixtures/approved generic guides
ไม่ส่ง private truth, credentials หรือข้อมูลผู้เรียนจริงไป provider
อ้างอิง [pricing](https://ai.google.dev/gemini-api/docs/pricing),
[API keys](https://ai.google.dev/gemini-api/docs/api-key),
[rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
ไฟล์นี้ติดตามงานค้างข้อ 12–13 และขอบเขตที่ยังไม่ได้อนุมัติ; ข้อ 11 ผ่าน local acceptance ตาม [ผลตรวจ](step-11-verification.md)

## Foundation ที่เพิ่มแล้ว

- fake embeddings แบบ deterministic, model fake-hash-16-v1, dimension 16, mode mock
- validation ปฏิเสธ dimension ผิด/NaN/Infinity; ไม่มี network หรือ credentials
- training incident-group metrics: duplicate/deleted/undetermined ไม่เปลี่ยน denominator,
  null พร้อมเหตุผลเมื่อตัวหารศูนย์ และรายงาน incomplete groups เมื่อ snapshot truncated
- tests ของ foundations อยู่ backend/tests/test_fake_embeddings.py และ test_evaluation_metrics.py

ผล foundation เดิม: pytest สองไฟล์ผ่าน 7 tests. ข้อ 11 เชื่อม metrics กับ evaluator/API/UI แล้วและเพิ่ม PostgreSQL/browser acceptance ตามผลตรวจด้านล่าง.
การจับ incident ใช้ evidence refs ของ detection เทียบกับ frozen expected evidence; manual tickets ไม่เข้าตัวหาร detection.

## 11 — ผ่าน local acceptance

- [x] Alembic evaluation/items และ immutable snapshot; evaluator DB grant แยก
- [x] Compose evaluator process ใช้ `evaluator_runtime`; claim, run-before-job lock และ lease fencing
- [x] finish cutoff/drain สูงสุด 60 วินาที; late analysis ถูก fence และไม่แก้ snapshot
- [x] Owner evaluation/export/completed training truth; assigned Instructor truth ก่อน finish/หลัง completion พร้อม audit; exam routes ยังไม่เปิด
- [x] Instructor account/quota/assignment สร้างผ่าน operator provisioning; comment/review ใช้ scoped API/UI และไม่แก้ assessment/note
- [x] A/B รัน detector จริงบนชุด event/truth เดียวกัน; C ส่งสถานะ unavailable จน provider/budget controls พร้อม
- [x] Next.js pending/result/export/Instructor UI; Chromium E2E finish→evaluation→JSON export ผ่าน
- [x] PostgreSQL regression ผ่าน cutoff, late AI, deleted ticket denominator, N/A metrics, grants, assignment และ immutability

ผลตรวจ 15 ต.ค. 2026: full CI integration script ผ่าน; PostgreSQL integration 50 passed,
Chromium E2E 11 passed, HTTP smoke 3 passed,
metrics/experiments 4 passed, OpenAPI approved-contract 1 passed; Ruff, mypy, ESLint และ Next typecheck ผ่าน.
มี deprecation/cache warnings ที่ไม่ทำให้ tests ล้ม. GitHub CI ยังไม่ได้รันสำหรับ changeset นี้.
Human scoring อยู่ N/A (`HUMAN_SCORING_POLICY_UNDECIDED`); rubric, retake และ override/revoke unlock ยัง pending.

## 12 — real adapter ใช้งาน local แล้ว; acceptance ข้อ 12 ยังไม่ครบ

- [x] config ปฏิเสธ real mode หากไม่ยืนยัน no-billing, synthetic-only หรือ model ที่อนุมัติ
- [x] runtime secret จำกัดให้ worker; API/browser ไม่ได้รับ key
- [x] adapter ตรวจ Pydantic/citation; เก็บ token usage และคิด quota เมื่อ invalid JSON มี usage
- [x] real timeout เก็บ reservation `unknown`; timeout/invalid output/retry integration ผ่าน PostgreSQL
- [x] bounded real call จาก UI/API/worker ใช้ S02 synthetic fixture และ Gemini 3.5 Flash-Lite Free Tier
- [ ] versioned rate card, component budget/reservation และ global caps
- [ ] 429 policy/backoff และขอบเขต retries/idempotency สำหรับ provider
- [ ] rate-limit/usage reconciliation failure และ production credential/privacy controls
- [ ] experiment C จริงจากข้อ 11; benchmark ยังไม่ทำ

ข้อ 12 หลักยังไม่ผ่านจนกว่าจะปิดรายการค้างด้านบน; การ real E2E local ไม่ใช่ benchmark

## 13 — storage/ingestion ยังต้องทำ

- [ ] ตรวจและ pin PostgreSQL/pgvector image/extension compatibility จริง
- [ ] Alembic kb schema, profiles, fixed dimension embeddings, manifests และ runtime grants
- [ ] approved Markdown corpus แยกจาก docs/fixtures/private truth; ระบุ reviewer/license/hash
- [ ] chunking/versioned ingestion jobs พร้อม dedupe/lease/resume และ component budget
- [ ] validate-before-publish immutable release, active pointer CAS, revoke ทุก projection
- [ ] pin release/config ต่อ run ใหม่; run เก่าไม่เปลี่ยน corpus เงียบ ๆ
- [ ] golden/held-out Thai/English tests ด้วย fake embeddings; ไม่อ้าง quality benchmark จริง
- [ ] PostgreSQL tests repeat ingestion, partial publish, dimension, ACL, revoke และ upgrade

## วิธีอัปเดตสถานะ

CI integration script รันทุก test ที่ติด integration marker; foundation แยกใน backend job
เพราะต้องอ่าน docs นอก test container. ข้อ 11 ผล local ล่าสุดบันทึกในส่วนด้านบน;
GitHub CI ของ changeset นี้ยังรอยืนยัน.

เติมผลคำสั่งและหลักฐานเมื่อทดสอบผ่านจริง แล้วจึงติ๊กเฉพาะรายการนั้น
ข้อ 11 ผ่าน local acceptance; checklist ข้อ 12–13 ยังไม่ผ่าน. GitHub CI ของ changeset นี้ยังรอยืนยัน.
rubric/retake/override-revoke unlock และ global provider controls ยัง pending ตาม SRS decision register
