# คู่มือทดสอบ Flow ทั้งระบบ — 28 ต.ค. 2026

ใช้กับ working tree ปัจจุบัน ไม่ใช่หลักฐานว่า production ผ่านแล้ว
เริ่ม local ที่ `http://127.0.0.1:4175/learning` โดย API/worker/evaluator ต้อง healthy
ดู [ผลตรวจ Dify/Tutor](dify-integration-verification.md), [ระบบปัจจุบัน](current-system.md) และ [คู่มือนำเสนอ](presentation-guide.md)

## เตรียมข้อมูลและบัญชี

ใช้ Analyst A, Analyst B และ Instructor ที่ได้รับ assignment ของ A จริง แยก browser profile/session
ไม่แก้คะแนนใน DB เพื่อทำให้ demo ผ่าน ไม่ล้าง Supabase เพื่อเตรียม tests
การทดสอบ destructive/concurrency/reset ใช้ PostgreSQL ทิ้งได้ชื่อ `soc_test_*` เท่านั้น
ไม่เปิด URL หรือ execute payload ในหลักฐานจำลอง

## Flow หลักที่ต้องเดินด้วยมือ

| ขั้น | เปิด/กดอะไร | สิ่งที่ต้องเห็น |
|---|---|---|
| 1 | Guest → ดูตัวอย่าง | ดู public demo ได้ ไม่เห็น progress/คำตอบ/ข้อมูล A หรือ B |
| 2 | สมัครด้วย email | validation ตรงกติกา ถ้าต้องยืนยัน email ให้แสดง pending ไม่แกล้ง login สำเร็จ |
| 3 | Email login / Google login | session จริง ชื่อบัญชีถูกต้อง เข้า login/register ขณะมี session แล้วไม่เห็นฟอร์มซ้ำ; Google ทดสอบด้วยบัญชีจริงหลังตั้ง callback |
| 4 | `/learning` ระดับต้น | เห็นบทเรียนจาก DB ระดับสูงยังล็อก ไม่ได้ผ่านเพียงเพราะเปิดหน้า |
| 5 | กดดู field ตัวอย่าง → บันทึกขั้น → refresh | ขั้นเรียนคงอยู่ ต้องทำตามลำดับ ทำครบแล้วกดจบบทเรียน เรียนครบทุกบทของระดับก่อนเริ่ม practical exam |
| 6 | ส่วน “ถามผู้ช่วยสอน AI” | ถ้ายังไม่รับรอง release ให้ปุ่มปิดและบอกเหตุผล ไม่เรียก paid provider เงียบ ๆ |
| 7 | เมื่อรับรอง Dify แล้ว ส่งคำถามทั่วไป | รับ 202 → queued/running → คำตอบพร้อม sources จาก DB; refresh/ปิด browser แล้วงานยังมีอยู่ ไม่มี key ใน browser |
| 8 | `/practice` เลือกเคสระดับต้น | เลือก evidence/severity/disposition/reason → บันทึกร่าง → refresh ได้ร่างเดิม |
| 9 | Submit practice | feedback ตามกฎจาก DB พร้อมเหตุผล/ข้อจำกัด ไม่อ้างว่า Dify ตรวจเหตุผลแล้วถ้ายังไม่ได้เชื่อม ใช้ผลนี้แทนสอบผ่านไม่ได้ |
| 10 | `/knowledge-check` ตอบครบ 10 ข้อ → ส่ง | ส่งทั้งชุดครั้งเดียว เก็บ immutable history; ปัจจุบัน needs_review ไม่มีคะแนนผ่านปลอม ไม่ถือว่าสอบเลื่อนระดับสำเร็จ |
| 11 | `/scenarios` → เลือก S02 → `/runs` เริ่ม | มี run จริง ปล่อยเฉพาะ due events ด้วย server clock; ปิด browser/logout ไม่หยุด worker |
| 12 | `/runs/{id}` → filters/event detail | อ่าน request/response/log แบบ escaped text; pause แล้วไม่มี future events ใหม่; resume แล้วไม่ซ้ำ |
| 13 | Alert → Ticket → Assessment/Note | อ้าง evidence ใน run เดียวกัน; create/edit/soft-delete/restore และดู revisions ได้ ข้อมูลไม่ถูกเขียนทับย้อนหลัง |
| 14 | เปิด ticket เดียวกันสองแท็บแล้วแก้ | แท็บ version เก่าได้ 409 และ draft ไม่หาย ไม่ overwrite งานอีกแท็บ |
| 15 | Finish training | รอบ completing/completed ปิด mutation รวม restore/note ไม่ใช่เปิดเฉลยข้อสอบ |
| 16 | กลับ `/learning` → เริ่ม practical exam | Backend ตรวจ gate/quota เลือก case ไม่เปิด Ask AI/คำใบ้; ห้ามอ่านประวัติ Tutor ผ่าน direct API ระหว่าง exam ค้าง |
| 17 | เลือก evidence → เหตุผล → submit | freeze คำตอบและ cutoff แก้ไม่ได้ refresh/double submit ไม่สร้างคำตอบใหม่ |
| 18 | Instructor `/instructor/exams` ตรวจ | เฉพาะ assignment หลัง submit มี audit; ไม่เปิดเฉลยเต็มให้ learner |
| 19 | Learner → ตรวจผลและสิทธิ์ล่าสุด | ผ่านเคสแรกเห็น 1/3 และเริ่มเคสถัดไป ผ่านครบ 3 เคสจึงเปิดระดับถัดไป ไม่เพิ่มคะแนนด้วย AI |
| 20 | ทำซ้ำระดับกลาง/ชำนาญ | บทเรียน/เคสแยกระดับ ผ่านทั้งหมดไม่แปลว่าฟีเจอร์ AI/สนามฝึกอิสระทุกแบบพร้อมโดยอัตโนมัติ |

## Negative / recovery checks

- บัญชี B เปิด UUID ของคำถาม/run/ticket ของ A ต้องไม่เห็นข้อมูล (404 เมื่ออยู่นอก scope)
- ไม่ส่ง CSRF/Origin ใน mutation ต้องถูกปฏิเสธ unknown fields/คะแนน/role ที่ client ใส่ต้องไม่ถูกเชื่อถือ
- ส่ง idempotency key เดิม/body เดิม ได้ resource เดิม; body ต่างได้ 409
- Tutor quota ใช้ ledger เดียวกับ logical AI requests เดิมของบัญชี ไม่เพิ่มเป็นอีก 20 แยกต่างหาก
- หลายบัญชี/หลาย worker ส่ง Tutor พร้อมกันต้องไม่ reserve เกินเพดาน US$0.25 รวม ไม่ใช่ต่อคน
- Provider timeout/crash หลัง dispatch: ไม่ retry อัตโนมัติ เงินที่ยังไม่ทราบผลคง hold; ไม่เดาว่าใช้ 0 และไม่สร้างคะแนนผ่าน
- Citations นอก document/chunk hash ที่รับรอง หรือ SOC-403 ที่ไม่มีใน retrieved sources: ไม่แสดง raw answer ให้ผู้เรียน
- ถอน policy/document/hash: คำตอบเก่าถูกซ่อนทั้ง history/detail ไม่กลับมาจาก refresh
- Provider ล่มไม่หยุดเรียน/สืบสวน/CRUD และไม่แปลว่าไม่มีภัย
- ทดสอบ 375/768/1440px, keyboard focus, labels, loading/empty/error/session expired และ log ที่มี HTML ต้องเป็นข้อความ
- ทดสอบ restart runner บนฐานทิ้งได้ ไม่สร้าง events/jobs ซ้ำ; ห้าม kill/reset ฐานจริงเพื่อสาธิต

## อะไรทำงานแล้ว และอะไรยังค้าง

| ส่วน | สถานะที่ควรอธิบาย |
|---|---|
| Supabase PostgreSQL/Auth | มี implementation และ local stack; Google OAuth จริง/confirmation ต้องมี manual acceptance ตาม environment |
| Lesson/practice/written persistence | ใช้ DB; ไม่ใช้ JSON ใน browser หรือ localStorage เป็นคะแนนจริง |
| Practical exam/review | มี flow; Instructor assignment และผลตรวจตาม rubric ไม่ใช่ AI auto-pass |
| Dify transport | key/app และหนึ่ง live Workflow call เคยสำเร็จ; โค้ด Tutor ใช้ pinned Workflow version ไม่ใช้ Chat API แทน |
| Tutor บนเว็บ | เพิ่ม API/DB/worker/UI แล้ว แต่ปิด real dispatch จน sources/release/cost bound รับรองครบ |
| Dify ตรวจข้อเขียน/เหตุผล/เคส | ยังไม่ implement task adapter เหล่านี้ ไม่เอา tutor prompt ให้คะแนนแทน |
| Citation quality | มี structural/hash guards; semantic grounding/Thai-English held-out benchmark ยังไม่ถือว่าผ่าน |
| งบจริง | มี reservation ceiling; ต้องตรวจ bound ของ flow รวม embedding และ reconcile usage ก่อนเปิดจริง ไม่อ้างว่าเป็น billing hard limit ของ Dify |
| Public deploy | ยังต้อง web/API/worker/evaluator, TLS/secrets/redirect/migrate/release/rollback/backup และ acceptance บน URL จริง |
| GitHub / วิดีโอ | working tree ยังไม่ commit/push ในรอบนี้, CI SHA ล่าสุดยังไม่ตรวจ; ยังต้องถ่ายคลิป ≤20 นาทีและเปิดสิทธิ์ลิงก์ |

## คำสั่งตรวจอัตโนมัติ

ใช้คำสั่งตาม AGENTS.md กับ runtime ที่ปักไว้ `pytest` integration ต้องกำหนด disposable DB ชัดเจน
Playwright ที่ mock routes พิสูจน์ UI เท่านั้น ไม่ใช้แทน live Google/Dify acceptance
เอกสารนี้เป็น test plan ไม่ติ๊กทุกขั้นว่าผ่านหากยังไม่ได้เดินจริงบน environment ที่จะส่งงาน
