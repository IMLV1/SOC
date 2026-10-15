# Prototype alignment

อัปเดต: 15 ตุลาคม 2026

เทียบกับ [Architecture](architecture.md), [API contract](api.md) และ [Development plan](development-plan.md)

## ข้อสรุป

ต้นแบบเดิมสอดคล้องในหน้าจอและ flow หลัก แต่มีพฤติกรรมขัดกับแผนใหม่หลายจุด รอบนี้แก้ **พฤติกรรม frontend ในขอบเขต mock** ให้ใช้เป็น reference สำหรับพัฒนาได้ โดยยังไม่อ้างว่า prototype คือ React frontend หรือ backend production ตามแผน

`prototype/` ยังคงเปิดด้วย static server ได้ ส่วน Next.js/React/TypeScript และ FastAPI/Python worker/PostgreSQL อยู่ในงาน `frontend/` และ `backend/` ตาม phase ที่กำหนด ไม่ย้ายไฟล์ทับต้นแบบตาม development-plan §5

## สิ่งที่ปรับในต้นแบบ

| หัวข้อ | ก่อนปรับ | หลังปรับ | ข้อกำหนด / route เป้าหมาย |
|---|---|---|---|
| Run lifecycle | Review → Completed ทันที | Reviewing → Completing → Completed; mock pending 1.5 วินาที | architecture §7; POST runs/{id}/finish |
| จบรอบ | ยังแก้ assessment/note/restore ได้ | read-only ตั้งแต่ Completing รวม Instructor status edit; comments ยังเพิ่มได้ | api §2, §7, §11 |
| Evaluation | คำนวณใหม่จากข้อมูลที่อาจถูกแก้ | snapshot ณ finish, release/assessment cutoff และ truncated flag | GET runs/{id}/evaluation |
| Export | ส่งออกได้ทุกสถานะ | Completed เท่านั้น | GET runs/{id}/export |
| Clock | logout/refresh พักรอบ | logout ไม่พัก; catch up จาก wall time เมื่อกลับมา | architecture §7; ยังจำลองใน browser |
| Concurrent runs | เริ่มรอบใหม่แล้วพักเก่าอัตโนมัติ | ปฏิเสธเมื่อมี running run ของบัญชีเดิม รวมตอน resume | runs create/resume + quota |
| Run quota | นับทุกวันที่เคยใช้รวมกัน | นับเฉพาะวัน UTC ของบัญชี; ปรับ limit ไม่ reset usage | GET me/quota; operator provisioning; ไม่มี public quota API |
| Registration | สมัครแล้ว login ทันที | สมัครสำเร็จกลับ Login; role Analyst เท่านั้น | POST auth/register / login |
| Evidence filters | keyword/source | เพิ่ม from/to ISO UTC, asset, username, IP และแบ่งหน้า | GET runs/{id}/events |
| Timestamp | เวลา 21:00 คงที่ | UTC ของ event ผูกกับ startedAt; timeline แสดง Asia/Bangkok | api §1, §6 |
| Assessment edit | ไม่ตรวจ version | expected_version กับ ticket revision; conflict เก็บ draft และ refresh ได้ | PATCH tickets/{id} |
| Assessment history | มี audit text อย่างเดียว | เก็บ learner revisions และปุ่มประวัติคำตอบ; Instructor ไม่เพิ่ม learner answer | GET tickets/{id}/assessments |
| Delete/restore | restore ไม่มีเหตุผล | confirm + reason + version check สำหรับ ticket/note | DELETE และ POST restore |
| Note edit | ไม่ระบุเหตุผล | บังคับ reason เก็บ version เดิมและ audit | PATCH notes/{id} |
| AI retry | Guest/รอบจบกดเปลี่ยน mock ได้ | จำกัดเฉพาะเจ้าของรอบที่ยังแก้ไขได้ | POST analyses/{id}/retry |
| เส้นทางเรียนรู้ | เข้า dashboard แล้วเลือกเคสได้ทันที | หน้าแรกเป็น 3 ระดับ; login แล้วสอนการใช้งาน; บทเรียนอ่าน request/response แบบกด 5 จุดก่อนเปิดเคสทดสอบ | [Learning path](learning-path.md) LEARN-01–03 |
| ข้อสอบเลื่อนระดับ | Ticket/AI brief บอกผลและ severity ตั้งต้น | รอบสอบซ่อนชื่อที่ใบ้ผล, initial severity, คำใบ้และ AI brief; ส่งคำตอบแล้วจึงได้ feedback และผ่านทุกเคสจึงเปิดระดับใหม่ | [Learning path](learning-path.md) LEARN-04–07 |

ชื่อสถานะใน UI เช่น `Investigating` เป็น display label ไม่ใช่ wire enum ใน API; backend client ใน Phase 0–3 ต้อง map เป็น `investigating` และใช้ UUID ไม่ใช้รหัสแสดงผล `TKT-1042` แทน UUID

## ส่วนที่ยังเป็น mock และไม่ควรนับว่าพัฒนาตาม architecture เสร็จแล้ว

| ส่วน | ข้อจำกัดปัจจุบัน | งานตามแผน |
|---|---|---|
| Transport | ไม่มี fetch ไป `/api/v1`, ไม่มี JSON response envelope/CSRF/Idempotency-Key จริง | SOC-001 ถึง SOC-004; generated client และ contract tests |
| Authentication | บัญชี @demo.test และรหัสเดโมคงที่ 12 ตัว; ไม่มี password hash/session cookie จริง | SOC-003; ไม่ใช้ชุดนี้บน public auth |
| Data model | JavaScript view model และ display IDs, localStorage; ไม่ใช่ UUID/SQL schema | SOC-001, SOC-006, SOC-010 |
| Concurrency | version check ในโมเดลเดียว; ไม่ใช่ atomic DB transaction และไม่รองรับแก้พร้อมกันหลายแท็บ | SOC-006, SOC-010 |
| Pagination | local pagination 10 รายการ; ไม่ใช่ cursor query ของ server | SOC-008 |
| Queue / clock | browser catch-up จำลองผลที่ควรเกิด ไม่ได้ประมวลผล background ขณะ browser ปิดจริง | SOC-006 |
| Completing | รอ mock timer ไม่ได้ drain worker jobs 60 วินาที | SOC-006, SOC-014 |
| AI | ผลจาก fixture และ fault toggle; ยังไม่มี analysis jobs/retry revisions/global token budget/provider | SOC-011, SOC-012 |
| Ground truth | ซ่อนใน UI จนจบ แต่ยังอยู่ใน JavaScript ฝั่ง client ไม่ป้องกันเปิด source | SOC-005, SOC-014 |
| Exam security | บทเรียน/ผลสอบอยู่ localStorage, demo กับข้อสอบยังใช้ fixture ชุดเดียวกันและคำตอบอยู่ฝั่ง browser; ห้ามถือว่าเป็นข้อสอบที่กันโกงได้ | LEARN-02/03; server-side gate, private exam bank/answer key, blind serializer |
| AI/RAG grading | ตรวจ 4 ข้อด้วย mock rubric; เหตุผลตรวจเพียงความยาว ไม่เข้าใจความหมายและไม่ค้น knowledge จริง | LEARN-03 และ [RAG §12](rag-langchain.md#12-learning-coach-และการประเมินเหตุผลหลังสอบ) |
| Security/ownership | ตรวจ flow ฝั่ง client เท่านั้น localStorage แก้ได้ | SOC-003, SOC-010 |
| Retention/audit | ไม่มี purge ตาม expires_at; audit ไม่ใช่ server append-only | SOC-010, SOC-016 |
| Experiment | แสดง Not measured; production A/B รัน detector จริงบน snapshot เดียวกัน, C คง unavailable จน global provider/budget controls พร้อม | POST admin/runs/{id}/experiments; SOC-014 |
| Instructor | prototype role state เป็น local; production มี assigned-run evaluation/truth review, comments และ access audit; account/quota/assignment ใช้ operator CLI | `/admin/runs*`; SOC-015 |

ข้อจำกัดเหล่านี้ไม่ใช่ข้อยกเว้นสำหรับระบบจริง ต้องทำให้ครบและผ่าน integration/E2E tests ก่อนนับ phase นั้นเสร็จ

## วิธีตรวจ flow ใหม่

1. Login Analyst ใหม่ → เห็นคำแนะนำ → เข้า “เรียนวิธีอ่าน request” ก่อน; ปุ่มเคสทดสอบยังล็อก
2. กด Method, Path, Response, บัญชี/IP, เหตุการณ์ต่อเนื่องทีละขั้น → จบบทเรียนแล้วเคสระดับเริ่มต้นเปิด
3. เริ่มสอบหนึ่งเคส → Event explorer เปิด request/response ได้ แต่ Ticket ไม่มี AI brief/คำใบ้และ severity เป็น Unrated ก่อนตอบ
4. ส่งคำตอบหลังหลักฐานครบ → เห็น rubric หลังส่ง; ไม่ผ่านแล้วกลับไปเริ่ม attempt ใหม่ได้ ผ่านทั้งสองเคสจึงเปิดบทเรียนระดับกลาง
5. ตรวจ flow เดิม: pause/clock, filters, version conflict, CRUD note/ticket, export lock, Completing/Completed และ Instructor comments ตามตารางด้านบน

การทดสอบอัตโนมัติอยู่ใน `prototype/tests/model.test.cjs` ผลตรวจ browser และข้อจำกัดการตรวจอัปเดตใน [Prototype QA](../prototype/QA.md)
