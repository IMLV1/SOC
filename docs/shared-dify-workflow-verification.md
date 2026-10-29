# Dify Workflow เดียวสำหรับ tutor และ feedback ข้อเขียน

ตรวจ 30 ต.ค. 2026 จาก base `b598c17` บน `main` ผลด้านล่างเป็น local tests ไม่ใช่ผล Dify live หรือ public deployment

## สถานะและเส้นทางข้อมูล

- ก่อนแก้: Tutor บทเรียนใช้ Dify Workflow API; ข้อเขียนเก็บ frozen submission เป็น `needs_review` แต่ไม่มี AI feedback
- หลังแก้ใน repository: ทั้ง `mode=tutor` และ `mode=grade` เรียก `POST /workflows/run` ผ่าน `DIFY_APP_KEY_FILE` เดียว เมื่อเปิด grade แล้ว Tutor จะส่ง `mode=tutor`; grade ส่ง `mode=grade` หลังส่งข้อเขียนแล้วเท่านั้น
- ข้อเขียน 10 คำตอบส่งเป็นหนึ่ง logical AI request ต่อ submission เพื่อให้ผู้ใช้ขอ feedback เมื่อพร้อม `POST /api/v1/learning/levels/{level_id}/written-submissions/{submission_id}/feedback` ทำ owner/CSRF/Origin/quota check แล้วบันทึก durable job; `GET` อ่านสถานะและผลของเจ้าของเท่านั้น
- Worker เรียก Dify นอก DB transaction, ไม่ส่งซ้ำเมื่อไม่ทราบผลการ dispatch, ตรวจ workflow_id, frozen question IDs ทั้ง 10, source document/chunk hash และ SOC section IDs ก่อนเก็บผล หากผลผิดรูปแบบ/provider ล่มให้ `needs_review` ไม่แสดง raw output
- Feedback ใช้ `supported|unsupported|insufficient` พร้อมคำอธิบาย/อ้างอิง ไม่แก้ frozen submission ไม่ให้คะแนนสอบ ไม่ปลดล็อกระดับ และไม่เปิด Ask AI ระหว่างข้อสอบภาคปฏิบัติค้าง
- Migration `0024_remove_tutor_daily_budget` ลบ hard gate US$0.25/วัน เพิ่ม `grade_enabled=false` และตาราง `app.written_feedback` พร้อม grants แยก API/worker; ยังเก็บ reserved USD/token usage ต่อคำขอและโควตา 20 logical AI requests/ผู้ใช้/วัน

## สิ่งที่ยังต้องทำก่อน grade ใช้ Dify จริง

1. Import/แก้ [Workflow DSL](../knowledge/dify/SOC-groq-import.yml) ใน Dify app **เดิม** ให้ Start รับ `mode` (`tutor`, `grade`) และ `question` ยาวได้ตาม contract แล้ว Test Run ทั้งสองโหมด โดย grade ต้องคืน JSON `items` 10 รายการใน `answer` และ `sources` ที่มี approved content/metadata จริง
2. Publish Workflow ใหม่ ตรวจ `workflow_id`, document IDs, chunk hashes, no-match, prompt injection, output length และการใช้ quota/cost ของทั้งสองโหมด การตรวจ version เป็นหลัง dispatch บน Dify Free; เมื่อ drift ระบบไม่แสดงผล
3. Operator สร้าง review file ใหม่ที่ผ่านการตรวจจริง โดยตั้ง `status=approved_for_tutor_and_grade`, `grade_mode_verified=true` และข้อมูล release/cost ตาม `app.tutor.release.reviewed_policy` แล้วรัน migration wrapper ก่อน activate ด้วย `python -m app.tutor.release --review-file <review.json> --expected-version <version> --enable-grade` ภายใต้ `migration_owner` เท่านั้น ห้ามใช้ review candidate เดิมเปิด grade โดยไม่มีการทดสอบ
4. Rebuild/deploy API และ worker **คู่กัน** กับ migration 0024; ตรวจ authenticated browser → API → DB → worker → Dify → validated feedback บน environment ที่จะใช้งาน หากยังไม่ Publish ให้คง `grade_enabled=false`; Tutor เดิมยังทำงานด้วย Workflow เดิมจนมีการ activate release ใหม่

## ผลตรวจ

- Backend Ruff lint/format, mypy ผ่าน; `pytest tests` บน PostgreSQL ทิ้งได้ `soc_test_grade` **422 passed, 1 skipped** (skipped เฉพาะ opt-in real Dify smoke)
- New integration: owner/CSRF/extra fields, idempotent grade request, cross-owner 404, one durable job/one mocked Workflow call, validated feedback, ไม่มี level unlock; ทดสอบ schema/source/ID ผิดรูปแบบด้วย
- Frontend ESLint และ typecheck ใน Linux container ผ่าน; production build `next build --webpack` ในสำเนาแยกผ่าน Turbopack บน mount ชั่วคราว panic จึงใช้ webpack ตรวจ source เดียวกัน
- Playwright ด้วย Chrome headless โปรไฟล์ชั่วคราว/route mocks: feedback หลัง submit, POST หนึ่งครั้ง, escaped HTML, ไม่อ้างคะแนนผ่าน **1 passed**
- ไม่มี real Dify call, ไม่มีการแก้ Workflow ใน Dify Cloud, ไม่มีการเปิด `grade_enabled` หรือ migrate Supabase production ในรอบตรวจนี้ ดังนั้น **grade ยังไม่พร้อมใช้งานจริงบนเว็บ local/public** จนทำ 4 ขั้นข้างบน

## ข้อจำกัด

Structural citation validation ยืนยันว่า source มาจาก corpus ที่อนุมัติและรหัสอ้างอิงปรากฏจริง แต่ไม่พิสูจน์ว่าคำอธิบายทุกประโยคถูกต้องเชิงความหมาย ต้อง benchmark/ตรวจตัวอย่างโดยคนก่อนอ้างคุณภาพหรือใช้ตัดสินคะแนนสอบ เพดานราคา $0.25/วันถูกยกเลิกตามผู้ใช้ แต่การใช้บริการภายนอกยังขึ้นกับ plan และโควตาฝั่ง Dify/Groq
