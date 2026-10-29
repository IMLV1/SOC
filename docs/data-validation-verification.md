# Data validation: ผลตรวจ 29 ต.ค. 2026

ตรวจและแก้ working tree บน `main` จาก base `991df5b` ผลในเอกสารนี้เป็น local acceptance ไม่ใช่ผล GitHub CI หรือ public deployment

## สิ่งที่แก้

1. ข้อความที่ต้องมีเนื้อหา เช่นเหตุผลข้อสอบ ชื่อ ticket คำถามและ comment ใช้ validation ที่ trim แล้วปฏิเสธข้อความว่าง รวมช่องว่าง Unicode ไม่ปล่อยให้ไปติด DB constraint เป็น 503 รหัสผ่านไม่ถูก trim และร่างฝึกที่ยังไม่ส่งยังเก็บ reason ว่างได้
2. `expected_version`, `expected_progress_version` และ seed ใช้ strict integer ปฏิเสธ boolean, string และ float แต่คง minimum/maximum และ UUID string ตาม contract เดิม
3. Client JSON ปฏิเสธ U+0000, unpaired Unicode surrogate และ nesting เกิน 64 ชั้นก่อน persistence ส่วน path/query ปฏิเสธ U+0000 ก่อน authentication/DB
4. จำกัด body `/api/v1/*` ที่ 1,048,576 bytes ก่อน session lookup/JSON parsing ตรวจขนาดจริงขณะรับ chunk ไม่เชื่อ Content-Length อย่างเดียว; เกินคืน 413 และ header ผิด/ซ้ำ/ความยาวไม่ตรงคืน 400 มี error envelope, request ID และ no-store โดยไม่สะท้อน input
5. Submit ข้อสอบใช้ validator ชุดเดียวกับ exam policy ปฏิเสธ evidence ซ้ำ และเปลี่ยนกรณีอ้าง evidence นอก snapshot จาก unhandled ValueError/500 เป็น 422 ภายใต้ transaction เดิม

ไม่แก้คะแนนผ่าน rubric โควตา roles หรือสิทธิ์ ไม่เพิ่ม migration และไม่เปลี่ยน Dify workflow/credentials

## ขอบเขตที่ตรวจ

ตรวจ 25 request-model families (รวม nested models และ empty logout body) และ 29 HTTP mutation routes จริง: auth/Google, training runs, ticket/note CRUD/restore, Instructor ticket/comment, analysis retry/questions, lesson progress, practice draft/answer, written submissions, Tutor และ exam start/submit/review

FastAPI เวอร์ชันนี้เก็บ included routers แบบ deferred และบาง routes ตั้ง `include_in_schema=False` จึงไล่ router จริงรวม hidden routes ไม่ใช้เฉพาะ OpenAPI เป็นตัวนับ มี assertion ว่ารายการไม่ว่าง และมี Tutor/exam submit อยู่จริง

| ขั้น | การตรวจและหลักฐาน |
|---|---|
| Transport | ขนาด 0/ต่ำกว่า/เท่ากับ/เกิน 1 MiB, chunked/ไม่มี Content-Length/แจ้งขนาดเท็จ, header ซ้ำ/ผิด, disconnect, safe error |
| JSON/schema | ทุก model รับ valid payload, ปฏิเสธ owner field ที่เกิน, UUID/enum/required/length/type, nested draft และข้อความ Unicode ผิดรูปแบบ |
| HTTP routes | ส่ง extra owner field ไปครบ 29 mutation routes และยืนยัน 422 ก่อน DB; malformed JSON, blank reason, duplicate evidence, boolean version และ query/filter/cursor/time/IP ผิดรูปแบบ |
| Auth/permissions | ชุด PostgreSQL regression ของ CSRF/Origin, session, owner/assignment, cross-run refs, exam gate, Instructor scope และ Supabase fake-provider integration |
| Domain/transaction | version conflict, idempotency, quota/concurrency, runner fencing, freeze/submit; เพิ่ม 6 invalid exam submissions และตรวจว่า attempt/version/answer ไม่เปลี่ยน ไม่มี answer หรือ idempotency record ค้าง จากนั้น valid concurrent submission ยังผ่าน |
| Database | fresh migrations/ledger, constraints/grants และ runtime roles จริงใน DB ทิ้งได้ `soc_test_foundation` ไม่ใช้ Supabase จริงเป็นฐานล้างทดสอบ |
| Output/AI | error ไม่สะท้อน secrets, response allowlists, citation/revocation/output regression; ใช้ fake/mock provider ไม่ยิง Dify จริง |

HTML/SQL ใน note ยังเป็นข้อความได้ตามปกติ ไม่ใช้การลบ keyword แทนการป้องกัน SQL injection/XSS: persistence ใช้ bound parameters และ UI แสดง escaped text

## ผลตรวจจริง

ใช้ Python 3.12/Pydantic 2.14.1 และเครื่องมือจาก image ทดสอบที่ pin ไว้ พร้อม source/fixtures/migrations ปัจจุบัน:

```sh
ruff check --no-cache app tests migrations ../scripts
ruff format --no-cache --check app tests migrations ../scripts
mypy --cache-dir /tmp/mypy-cache app
python -m pytest tests -q -p no:cacheprovider --tb=short -rs
```

- Ruff check/format ผ่าน
- mypy ผ่าน 104 source files
- pytest **415 passed, 1 skipped** (69.68 วินาที) รวม boundary tests ใหม่ 135 tests และ PostgreSQL integration
- test ที่ข้ามคือ `test_tutor_live.py` ซึ่งต้อง opt-in เรียก Dify จริง ไม่ได้ลด assertions หรือข้าม tests ที่ล้ม
- Foundation/OpenAPI drift รวมอยู่ในผลข้างต้นและผ่าน; ไม่มีการเปลี่ยนรูป schema ที่ทำให้ generated DTO เปลี่ยน
- `python ../scripts/generate-client-types.py --check` ผ่าน
- `git diff --check` ผ่าน

การเตรียมรอบแรกพบ image เก่ามี fixtures ไม่ครบ และไฟล์รหัสทดสอบเดิมสั้นกว่านโยบาย จึงเปลี่ยนมา mount source/fixtures ปัจจุบันและสร้าง random credentials เฉพาะฐานทิ้งได้ ไม่ลด validation และไม่แก้ secrets ของระบบจริง

## Local runtime และข้อจำกัด

Build API แบบ incremental จาก base image ที่ใช้อยู่ โดยตรวจ SHA-256 ของ uv.lock ให้ตรง checkout ก่อน ไม่มีการอัปเกรด dependencies; clean build แบบ offline ติดขั้นดาวน์โหลด uv จึงไม่อ้าง clean-from-registry build ผ่าน

นำ image ใหม่ขึ้นเฉพาะ local API ด้วย compose config เดิม และเก็บ `soc-supabase-api:before-validation-20261029` ไว้ rollback ไม่รัน migration/seed และไม่ restart worker/evaluator

ตรวจผ่าน Next.js proxy ที่เว็บ port 4175 ใช้จริง: `/health/ready` ได้ `200 ready`, body เกินขนาดได้ `413 PAYLOAD_TOO_LARGE`, query ที่มี U+0000 และ boolean seed ได้ `422 VALIDATION_ERROR` ไม่ใช้บัญชีจริงหรือสร้างข้อมูลทดสอบใน Supabase; API/worker/evaluator ยัง healthy หลังเปลี่ยน image

ผลทั้งหมดไม่ได้พิสูจน์ว่าไม่มีช่องโหว่ทุกชนิด ยังต้องยืนยัน GitHub CI ของ commit ที่ส่งจริง และ HTTPS/proxy/rate limits/acceptance บน hosting สาธารณะ ไม่เรียก real Dify ในงานนี้และไม่อ้าง provider benchmark ใหม่
