# ผลตรวจ Dify Workflow สี่โหมด — 30 ต.ค. 2026

## สิ่งที่เปิดใช้

- Dify app `SOC` Published version **#8**, Workflow ID `3d57b37b-47c3-4321-91ed-e7a994a3a6f5` รับ `mode=tutor|grade|practice|analyze` ผ่าน `/workflows/run` และคืน `mode`, `answer`, `sources`. Backend ตรวจ Workflow ID, mode, schema, approved document/chunk hash และ citations ก่อนบันทึกผล ไฟล์ DSL ใน repository คือ [SOC-groq-import.yml](../knowledge/dify/SOC-groq-import.yml); Grade ใช้ `json_object` และ `max_tokens=8192` เพื่อให้ JSON 10 ข้อไม่ขาดกลางทาง
- Supabase SOC schema อัปเกรดด้วย `app.db.migrate` ไป `0025_dify_practice_and_analysis` โดย checksum ledger ตรง Operator เปิด policy version **4** พร้อมทั้งสี่โหมด (`enabled`, `grade_enabled`, `practice_enabled`, `analysis_enabled`). API และ worker ใช้ `SOC_AI_PROVIDER=dify` และ secret file mount ฝั่ง server; ไม่แสดง key ใน frontend/เอกสาร
- `/practice` ให้ถาม AI หลังส่งคำตอบเคสแล้วเท่านั้น เก็บคำถาม งาน และผลใน `app.practice_ai_questions`; คำตอบมีแหล่งอ้างอิงจากคู่มือ ไม่เปลี่ยน deterministic case feedback หรือคะแนนสอบ. `/runs` วิเคราะห์หลักฐานที่ปล่อยแล้วผ่าน Dify แบบ advisory และบันทึกผลแยกจาก human assessment

## หลักฐานการตรวจ

- เรียก Published API ด้วยข้อมูล **จำลอง** ครบสี่โหมด Tutor, grade (ข้อเขียน 10 ข้อ), practice และ analyze: HTTP 200, Workflow ID เดียวกัน, sources 4 ชิ้นต่อโหมดที่ hash ตรง approved corpus; `validate_outputs`, `validate_feedback` (10 รายการ) และ `validate_analysis_outputs` ผ่าน. เคส analyze ตัวอย่าง GET `/admin` + 403 คืน severity/confidence `low` พร้อมข้อจำกัด ไม่สรุปว่าโจมตีสำเร็จ
- ทดสอบ integration บน PostgreSQL ทิ้งได้: **105 passed, 1 skipped**; HTTP smoke **3 passed**, worker/evaluator check ผ่าน. Browser suite รอบสุดท้าย **72 passed, 1 skipped, 0 failed** จาก 73 รายการ รวมการถาม AI หลัง submit และการกู้ประวัติหลัง refresh. Unit tests **325 passed** (106 integration deselected)
- Ruff check/format, mypy, frontend lint, production build, OpenAPI validator, generated client check และ local Markdown links ผ่าน; local Supabase API, worker, evaluator healthy, `GET /health/ready` ตอบ ready และ `/practice` ตอบ 200. การทดสอบ Dify API เป็น direct API + validators; ยังไม่ได้ยืนยันการกดทุก flow ด้วยบัญชีจริงบน Supabase browser

## ข้อจำกัด

- ผล LLM เปลี่ยนได้ แม้ sample ผ่าน; เมื่อ output/citation ผิด schema หรือ provider ล่ม ระบบใช้ `needs_review`/unavailable แทนการให้คะแนนหรือเดาแทน. การตรวจ source hash ไม่รับรองความถูกต้องทุกประโยคเชิงความหมาย
- Dify Free เรียก published-latest แล้วตรวจ Workflow ID **หลัง** dispatch; ถ้ามีการ Publish ใหม่ต้องตรวจและ activate release policy ใหม่ ไม่แอบใช้เวอร์ชันที่เปลี่ยนไป
- ยังไม่มี public deployment, production backup/restore drill หรือ benchmark RAG แบบ held-out; CI mock ไม่ใช่หลักฐานคุณภาพ LLM จริง
