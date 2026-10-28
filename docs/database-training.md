# บทเรียนและแบบฝึกบนฐานข้อมูล

อัปเดต 22 ต.ค. 2026 — ใช้แทน runtime preview จาก JSON เดิม ไม่แทนข้อกำหนดสอบใน SRS

## Flow ที่เปิดใช้

1. `/learning`: login → เลือกบทจากสารบัญ DB → เปิดคำอธิบาย → บันทึกขั้น → จบบท
   มี 3 ระดับ / 9 บท / 45 ขั้น ต้องทำบทก่อนหน้าให้ครบก่อนบันทึกบทถัดไป
   ระดับ 2/3 ต้องมี `level_unlocks` จากข้อสอบเดิม ไม่ปลดล็อกจากการเปิดอ่านหรือผลฝึก
2. `/practice`: เลือกระดับ/หมวด/เคส → อ่าน request/response/log ที่ escaped → เลือกหลักฐาน
   → บันทึกร่างหรือส่งคำตอบ → feedback พร้อมประวัติส่วนตัว เปิดใหม่ยังอ่านข้อมูลจาก server ได้
   30 เคส ระดับละ 10 หมวด authentication/web/access/change/data/evidence/anomaly/availability
   จำนวนต่อหมวดไม่เท่ากัน ไม่ใช่ 10 เคสต่อทุกหมวด
3. `/knowledge-check`: เรียนครบทุกบทของระดับ → เขียนตอบ 10 คำถาม → ส่งครบทั้งชุด
   เก็บ snapshot คำถามและคำตอบแบบ immutable; สถานะ `needs_review` ไม่มีคะแนนหรือ unlock
   **เป็นการทบทวนข้อเขียน ไม่ใช่ formal exam attempt** ยังไม่เปิดตัวตรวจข้อเขียนหรือเกณฑ์ผ่านใหม่
4. ข้อสอบภาคปฏิบัติอยู่ `/learning` ส่วน “ข้อสอบภาคปฏิบัติ” หลังจบบทเรียน
   ใช้ exam lifecycle/Instructor review เดิม เพิ่มตรวจ prerequisite ทุกบทจาก DB
   exam bank มี 3 เคสต่อระดับ รวม 9 เคส แยกจากชุดฝึก ไม่เปลี่ยน rubric/retake เดิม
5. `/demo` อ่าน benign examples จาก DB แบบสาธารณะ ไม่บันทึกคะแนน
   `/demo/learning` redirect `/learning`; `?view=practice` redirect `/practice`

## ความหมายของสี

- เขียว/ข้อความ “ถูกต้อง”: severity+disposition ตรงเฉลยฝึกที่อยู่ฝั่ง server
- แดง/ข้อความ “ยังไม่ถูก”: อย่างน้อยหนึ่งค่าต่างจากบริบทที่กำหนดไว้
- ความครบของ evidence ตรวจชุด ID แยกต่างหาก อ้างข้ามเคสหรือ ID ที่ไม่มีจริงถูกปฏิเสธ
- เหตุผลของผู้เรียนถูกเก็บ แต่ยังไม่ตรวจความหมายจาก Dify ไม่ใช้จำนวนตัวอักษรแทนความถูกต้อง
- ข้อสรุปอ้างอิง/เหตุผล/ข้อจำกัดแสดงหลังส่งฝึกเท่านั้น ไม่ใช่เฉลยข้อสอบ
- ผลฝึกไม่ใช่คะแนนสอบ ไม่เปลี่ยน assessment ของคน ไม่สร้างผลผ่านหรือ unlock

## Schema ใหม่: migration 0022_database_training

| ตาราง | เนื้อหา / สิทธิ์ runtime |
|---|---|
| `app.demo_events` | ตัวอย่างสาธารณะ เฉพาะ API SELECT |
| `app.practice_cases` | metadata/category/level/version/published evidence; API SELECT |
| `private.practice_truths` | severity/disposition/evidence/คำอธิบาย/ข้อจำกัด; API ไม่มี SELECT |
| `app.practice_drafts` | owner+case, draft, expected_version และ updated_at |
| `app.practice_answers` | append-only answer, frozen evidence, version, idempotency/hash, feedback |
| `app.written_questions` | 10 prompts ต่อ level, UUID/version/ordinal/category |
| `app.written_submissions` | owner/level, frozen questions+10answers, idempotency/hash, needs_review |

ความสัมพันธ์: user → drafts/answers/submissions, level → lessons/cases/questions,
practice case/version → immutable answers; ไม่มีข้อมูล authoritative ใน localStorage

`private.review_practice(actor,answer)` เป็น SECURITY DEFINER fixed search_path ตรวจเจ้าของ
และมี submission จริงก่อนอ่านเฉลย/เขียน feedback ใน transaction เดียว
API ไม่มี UPDATE/DELETE สำหรับ answers/submissions และไม่มี SELECT private practice truth
Practice feedback function ไม่อ่าน exam truth; API ไม่ import operator content

## API additions

| Method | Path | Behavior |
|---|---|---|
| GET | `/api/v1/practice/cases` | catalog พร้อม available ตาม level gate |
| GET | `/api/v1/practice/cases/{id}` | published evidence + ร่างของบัญชี ไม่ส่งเฉลย |
| PATCH | `/api/v1/practice/cases/{id}/draft` | `{expected_version,answer}`; conflict 409 |
| POST | `/api/v1/practice/cases/{id}/answers` | `{evidence_ids,severity,disposition,reason}` + Idempotency-Key UUID |
| GET | `/api/v1/practice/cases/{id}/answers` | ประวัติของบัญชี ล่าสุดไม่เกิน 50 ชุด |
| GET | `/api/v1/learning/levels/{id}/written-questions` | 10 ข้อ หลังบทเรียนครบและ level unlocked |
| POST | `/api/v1/learning/levels/{id}/written-submissions` | `{answers:[{question_id,answer}]}` 10 ข้อ + Idempotency-Key |
| GET | `/api/v1/learning/levels/{id}/written-submissions` | frozen history ของบัญชี ล่าสุดไม่เกิน 50 ชุด |

ใช้ JSON strict/unknown fields forbidden, CSRF+Origin ทุก mutation, Analyst only,
owner guard ก่อน idempotency replay; key เดิม/body ต่าง 409; ไม่อ้างอิง UUID ข้ามเคส/ระดับ
มี practical exam ที่ active/submitted/needs_review จะปิดการเข้าถึงเครื่องมือฝึก/ข้อเขียน
API ชุดนี้ใช้ explicit response models และ frontend typed DTO; ยังไม่เปลี่ยนเป็น approved OpenAPI
โดยอัตโนมัติจากการเขียนโค้ด

`GET /learning-path` เปลี่ยนเป็น metadata จาก DB; DB ไม่พร้อมคืน 503 ไม่ fallback static
`GET /lessons/{id}` และ mutation อ่าน published content/version/step list จาก DB
ขีดจำกัดบันทึกขั้นเรียน 60/min/IP รองรับ 18 saves ต่อระดับ; login/register ยังคง 10/min/IP+email
ความถูกต้อง step order/version/level gate ยังบังคับใน transaction ไม่ขึ้นกับ rate limit

## Seed และ artifact boundary

ต้นฉบับ lesson: `backend/fixtures/learning/curriculum-v1.json`
ชุดฝึก/คำถามที่เขียนเพิ่ม: `backend/operator_content/training_bank.py`
ไฟล์เป็น **operator seed source** ไม่ใช่ runtime database และไม่ส่งให้ browser
`app.learning.seed_full` ใช้ migration role/transaction/advisory lock ตรวจ immutable hash ก่อน insert
`app.db.seed_all` เรียก seed นี้หลัง schema พร้อม ไม่รัน seed ใน API startup

API image ไม่มี fixtures/operator_content; worker ยังใช้ version-pinned synthetic event fixtures
ของ simulation เดิมในการปล่อย due events ส่วน released events/jobs/history เก็บใน DB
ไม่ได้เปลี่ยน runner ให้สร้าง event จาก AI หรือย้าย future schedules เข้าสู่ public API
ถอด JSON public snapshots และ reader/workbench เก่าออกจาก frontend แล้ว
`prototype/` คงเป็น reference เดิม ไม่ย้ายมาทับแอป

## สิ่งที่ยังไม่พร้อม

- Dify Chatflow/Workflow ยังไม่เชื่อม; ไม่เรียก provider จริง ไม่มีค่าใช้จ่ายในงานนี้
- การประเมินข้อเขียน 10 ข้อ/คะแนนผ่าน/gate เข้ากับ formal exam ยังไม่ implement
  ไม่ใช้ needs_review เป็นผลผ่าน และไม่ยกเว้น practical exam เดิมเงียบ ๆ
- เพิ่ม formal exam bank ระดับกลาง/ชำนาญแล้ว แต่การตรวจคุณภาพเนื้อหากับผู้เรียนจริงยังค้าง
- ดังนั้นยัง **ไม่ใช่** “เหลือแค่ใส่ API key แล้ว deploy” ต้องตรวจ integration/acceptance ข้างต้นด้วย
- GitHub CI ล่าสุดของ working tree และ production/HTTPS/backup-restore ยังไม่ได้ยืนยัน

ใช้ skill write-clean-code แยก seed/public serializers/private feedback และ frontend-design
คง UI/ฟอนต์เดิมตามผู้ใช้ ไม่ redesign; เพิ่มสีที่มีข้อความกำกับโดยไม่แสดงผลปลอม

## ผลตรวจ 22 ต.ค. 2026

Source: working tree บน `main` หลัง `a1fc962` (ยังไม่ commit/push ในงานนี้)

- Backend `ruff check`, `ruff format --check`, `mypy app` (95 modules) ผ่าน
- `python -m pytest -q -p no:cacheprovider`: **247 passed** รวม real PostgreSQL
  แบบทิ้งได้ `soc_test_training_20261022`, runtime roles จริง และ fake Auth/Dify boundaries
  ไม่ใช่ cloud authentication benchmark
- ตรวจ fresh migration/transaction rollback/repeat wrapper/checksum, seed ซ้ำ,
  expected_version race, submit duplicate/key conflict, cross-case refs/ownership,
  direct private truth SELECT denied และ immutable answers UPDATE denied
- ทดสอบ 9 practical cases ผ่าน learner submit → assigned Instructor review →
  earned unlock ระดับ 2/3 จริง ไม่มีการ seed ผลผ่าน; fixture ตั้ง prerequisite สำหรับชุดนี้
  ส่วน ordered lesson save ตรวจผ่าน API ในชุดแยก
- Frontend lint/production build/TypeScript ผ่าน; Node tests **16 passed**
  รวม asset leakage guard และไม่ใช้ JSON/localStorage เป็น runtime content
- Browser regressions **28 passed** บน 4175 แบบ mock API boundary:
  drafts/reload/409/escaped logs, 10-answer batch/history, 375/768/1440px,
  auth redirects, Google และ Instructor/learning projections
- Browser live บน production build ที่ 4180 + API/worker/PG แยก: **2 passed**
  practice journey ไม่ mock ตั้งแต่ register → draft → correct/incorrect → reload/history;
  learning journey ใช้ API จริงจน submit/needs_review และทดสอบ 3 บทก่อนเริ่มสอบ
  ช่วง UI feedback/retake ภายหลังของ `learning.spec.ts` ใช้ mocked Instructor fallback
  เพราะไม่ได้ provision browser Instructor ใน harness นี้; ไม่อ้างว่าช่วงนั้นเป็น live review
- Supabase จริงใช้ wrapper migrate ถึง `0022_database_training` และ one-shot seed สำเร็จ:
  3 levels, 9 lessons, 30 practice cases (10/level), 30 written questions,
  2 public examples, 9 practical cases (3/level)
- เช็ก API role อ่าน private practice truth โดยตรงไม่ได้; API artifact ไม่มี fixtures/operator_content
- เว็บ 4175 `/health/ready` 200; API/worker/evaluator healthy
- ไม่สร้างบัญชี/คะแนน/คำตอบทดสอบใน Supabase; negative cloud query/health เป็น read-only
- Git diff whitespace และ local Markdown links ผ่าน; GitHub CI ของ working tree **รอยืนยันบน GitHub**

คำสั่งหลักจาก backend runtime ตาม lockfile:

```bash
ruff check app tests migrations ../scripts operator_content
ruff format --check app tests migrations ../scripts operator_content
mypy app
python -m pytest -q -p no:cacheprovider
python ../scripts/generate-client-types.py --check
```

Integration ต้อง opt-in ฐาน `soc_test_*` แยกทิ้งได้เท่านั้น ไม่ตั้ง reset ไปที่ Supabase
Frontend: `npm run lint`, `npm run build`,
`node --test tests/assets.test.mjs tests/database-training.test.mjs tests/supabase-config.test.mjs`
Browser mock ใช้ `database-training.spec.ts` และ regression auth/run/Google/learning/review;
browser live ใช้ `database-training-live.spec.ts learning.spec.ts` บน stack ทิ้งได้
