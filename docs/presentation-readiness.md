# สถานะพร้อมส่งงานและข้อที่ยังขาด

ตรวจ 27 ต.ค. 2026 บน working tree หลัง `a1fc962` (มีงานยังไม่ commit)
รายงานนี้แยก implementation, local verification และ public deployment ออกจากกัน

## Deliverables ทั้ง 6 ข้อ

| สิ่งส่งมอบ | มีแล้ว | ยังต้องทำ/ยืนยันก่อนส่ง |
|---|---|---|
| Core functions / CRUD / validation / responsive | บทเรียน, practice/ข้อเขียนเก็บ DB, simulation, ticket/note CRUD+history, practical exam/review; tests แยก server/browser | Dify chatbot และการตรวจเหตุผลข้อเขียนยังไม่พร้อม; ทดสอบ end-to-end ด้วยบัญชีจริงบน URL deploy หลังตั้ง provider/environment |
| SRS + Use cases + ER/schema | srs.md, api.md, database.md และ current-system.md สรุป flow/use cases/ER ล่าสุด | ตรวจรับ requirement ที่ยัง pending โดยเฉพาะข้อเขียน/AI grading; เอกสาร implementation ไม่ได้อนุมัติเปลี่ยน rubric |
| UI Prototype | prototype/ เป็น HTML/JS reference และมีเว็บจริงแสดง flow | ใช้ flow/screenshots ล่าสุดประกอบ เพราะ prototype เก่าไม่เท่ากับ runtime Supabase; หากวิชาบังคับ Figma เพิ่มต้องทำตาม rubric ของวิชา |
| GitHub collaboration | local history มี branch/merge/PR เดิม | งาน working tree ล่าสุดยังไม่ publish; GitHub CI SHA ล่าสุด/Issues/required checks ยังไม่ได้ยืนยัน ห้ามสร้างประวัติร่วมงานปลอม |
| Public deployed application | Supabase DB/Auth และ local stack | ยังไม่ยืนยัน full public web+API+worker+evaluator, migration/release/rollback, TLS/cookies/Google redirect บน URL จริง; preview auth-only เดิมไม่ใช่ full deployment |
| Video demo ≤20 นาที | มี presentation-guide.md และลำดับ demo | ยังต้องถ่ายสมาชิกทุกคน เปิดกล้อง อัปโหลดและทดสอบสิทธิ์ลิงก์ ไม่มีหลักฐานว่าส่งวิดีโอแล้ว |

ดังนั้น **ยังไม่ควรประกาศว่าครบทุก deliverable หรือ production-ready**

## สิ่งที่แก้ในรอบนี้

- Learning UI แสดงจุดเริ่มเล่นและแยกเรียน/ฝึก/ข้อเขียน/สอบ ไม่ใช้ลิงก์ไป anchor ที่ไม่มี section
- API ส่ง `level_statuses` เฉพาะบัญชีตนเอง: unlocked, all_lessons_completed, exam_case_count และ passed_case_count โดยไม่เปิดเฉลย
- แก้ผ่านเคสสอบแรกแล้วไม่เห็นทางเริ่มเคสถัดไป แสดงผ่าน X/3 และยังไม่ปลดล็อกจนกติกา server อนุญาต
- ปุ่มตรวจผล/สิทธิ์ใหม่ช่วยรับผล Instructor โดยไม่สร้างคะแนนหรือแก้ rubric
- Retry โหลดข้อเขียนระดับเดิมไม่ล้างคำตอบที่ยังไม่ส่ง และล็อกฟอร์มระหว่าง submit
- ล็อกแบบฟอร์ม practice ระหว่างบันทึก/ส่ง ป้องกันแก้ร่างแข่งกับคำตอบ async ที่กลับมา
- แก้ข้อความแนะนำ JSON runtime เก่าและข้อความ provider ที่ทำให้เข้าใจว่า Gemini เปิดใช้จริง
- เพิ่มเอกสาร flow, architecture, ER/use cases, audit deliverables และคู่มือนำเสนอ

## การตรวจรับรอบนี้

ผลคำสั่งและข้อจำกัดจะบันทึกในส่วนนี้หลังรันครบ ไม่ใช้สถานะ checkbox แทนผลทดสอบ

- Backend offline: Ruff + mypy ผ่าน; unit tests 152 passed (95 integration deselected)
- Frontend isolated production build/lint/TypeScript ผ่าน; Node tests รวม asset leakage guard 16 passed
- Backend เต็มชุดกับ PostgreSQL ทิ้งได้ `soc_test_presentation_20261027`: **247 passed** รวม owner isolation, ผ่านเคสทีละระดับและ persistence/concurrency เดิม; generated client types check ผ่าน
- Browser regressions: **31 passed** รวมผ่านเคส 1/3 และ 3/3, retry ข้อเขียนไม่หาย, draft conflict/XSS escaping, auth navigation และ responsive 375/768/1440; API boundaries ใช้ route mocks
- การทดสอบ browser แบบ route mocks พิสูจน์พฤติกรรม UI ไม่ใช่ live Supabase OAuth/Dify acceptance
- ไม่เรียก Dify จริง ไม่ deploy ไม่สร้างคะแนนผ่านหรือคำตอบผู้เรียนปลอมใน Supabase
- Local API อัปเดต learning projection แล้ว `/health/ready` ที่พอร์ต 8440 ตอบ ready; image ใช้ cached API เดิม + 2 ไฟล์ learning ที่ทดสอบ (full Docker build ค้าง remote metadata จึงหยุด ไม่อ้างว่าเป็น production release build)
- Markdown local links และ `git diff --check` ผ่าน เก็บกวาด container/network PostgreSQL tmpfs เฉพาะงานแล้ว ไม่ลบฐานข้อมูลผู้ใช้

คำสั่งหลักที่ใช้: backend `pytest -q -p no:cacheprovider` กับ disposable PostgreSQL และ `generate-client-types.py --check`; frontend `npm run lint`, `npm run build`, Node tests 3 ไฟล์ (`assets`, `database-training`, `supabase-config`) ใน isolated container; Playwright 9 spec files (`auth-navigation`, `database-training`, `exam-review`, `google-login`, `knowledge-check-resilience`, `learning-interaction`, `learning-progression`, `run-start-feedback`, `supabase-auth`) บน local dev server โดย mock API; `python3 scripts/check-doc-links.py` และ `git diff --check`

## งานค้างที่ต้องปิด

### Dify/RAG

ต้องกำหนด app/workflow, approved corpus, structured output/citations/revocation, usage/budget, timeout/retry policy และ secret ฝั่ง server ก่อนเปิด real calls
เชื่อม chatbot ตอนเรียน/ฝึกโดยไม่เปิดคำใบ้ระหว่างสอบ; ตรวจข้อเขียนหลัง freeze ตาม contract ที่อนุมัติ
เมื่อ provider ล่ม/หลักฐานไม่ครบให้รอตรวจ ไม่ auto-pass จากความยาวคำตอบ และไม่ใช้ mock เป็นผล benchmark

### Public deployment

เลือก hosting และตั้ง web/API/worker/evaluator ให้ครบ ใช้ runtime roles แยก migration one-shot และตรวจ source SHA/CI
ตั้ง secrets/TLS/cookie/CSRF/origin, Supabase Site URL/redirect และ Google provider ให้ตรง URL จริง
ตรวจ restore/rollback และเดิน flow ด้วยบัญชีจริง รวม logout/ปิด browser แล้วยังมี runner
Supabase เป็นฐานข้อมูล/Auth ไม่ได้ host Python worker ให้โดยอัตโนมัติ

### Repository และคลิป

ตรวจ diff/secret ก่อน commit เฉพาะไฟล์งาน แล้ว push/PR/merge ตามสิทธิ์ผู้ใช้ ตรวจ GitHub CI ของ SHA ที่จะ deploy
จัด Issues และการแบ่งงานตามการทำงานจริง ถ่ายคลิปตาม [คู่มือนำเสนอ](presentation-guide.md)

## อ้างอิง

[ระบบปัจจุบันและแผนภาพ](current-system.md) · [ฐานข้อมูลฝึก](database-training.md) · [Supabase](supabase-verification.md) · [Checklist](implementation-checklist.md)
