# Prototype alignment

อัปเดต: 12 ตุลาคม 2026

เทียบกับ [Architecture](architecture.md), [API contract](api.md) และ [Development plan](development-plan.md)

## ข้อสรุป

ต้นแบบเดิมสอดคล้องในหน้าจอและ flow หลัก แต่มีพฤติกรรมขัดกับแผนใหม่หลายจุด รอบนี้แก้ **พฤติกรรม frontend ในขอบเขต mock** ให้ใช้เป็น reference สำหรับพัฒนาได้ โดยยังไม่อ้างว่า prototype คือ React frontend หรือ backend production ตามแผน

`prototype/` ยังคงเปิดด้วย static server ได้ ส่วน React/TypeScript/Vite และ API/worker/PostgreSQL อยู่ในงาน `frontend/` และ `backend/` ตาม phase ที่กำหนด ไม่ย้ายไฟล์ทับต้นแบบตาม development-plan §5

## สิ่งที่ปรับในต้นแบบ

| หัวข้อ | ก่อนปรับ | หลังปรับ | ข้อกำหนด / route เป้าหมาย |
|---|---|---|---|
| Run lifecycle | Review → Completed ทันที | Reviewing → Completing → Completed; mock pending 1.5 วินาที | architecture §7; POST runs/{id}/finish |
| จบรอบ | ยังแก้ assessment/note/restore ได้ | read-only ตั้งแต่ Completing รวม Instructor status edit; comments ยังเพิ่มได้ | api §2, §7, §11 |
| Evaluation | คำนวณใหม่จากข้อมูลที่อาจถูกแก้ | snapshot ณ finish, release/assessment cutoff และ truncated flag | GET runs/{id}/evaluation |
| Export | ส่งออกได้ทุกสถานะ | Completed เท่านั้น | GET runs/{id}/export |
| Clock | logout/refresh พักรอบ | logout ไม่พัก; catch up จาก wall time เมื่อกลับมา | architecture §7; ยังจำลองใน browser |
| Concurrent runs | เริ่มรอบใหม่แล้วพักเก่าอัตโนมัติ | ปฏิเสธเมื่อมี running run ของบัญชีเดิม รวมตอน resume | runs create/resume + quota |
| Run quota | นับทุกวันที่เคยใช้รวมกัน | นับเฉพาะวัน UTC ของบัญชี; ปรับ limit ไม่ reset usage | GET me/quota; admin quota PATCH |
| Registration | สมัครแล้ว login ทันที | สมัครสำเร็จกลับ Login; role Analyst เท่านั้น | POST auth/register / login |
| Evidence filters | keyword/source | เพิ่ม from/to ISO UTC, asset, username, IP และแบ่งหน้า | GET runs/{id}/events |
| Timestamp | เวลา 21:00 คงที่ | UTC ของ event ผูกกับ startedAt; timeline แสดง Asia/Bangkok | api §1, §6 |
| Assessment edit | ไม่ตรวจ version | expected_version กับ ticket revision; conflict เก็บ draft และ refresh ได้ | PATCH tickets/{id} |
| Assessment history | มี audit text อย่างเดียว | เก็บ learner revisions และปุ่มประวัติคำตอบ; Instructor ไม่เพิ่ม learner answer | GET tickets/{id}/assessments |
| Delete/restore | restore ไม่มีเหตุผล | confirm + reason + version check สำหรับ ticket/note | DELETE และ POST restore |
| Note edit | ไม่ระบุเหตุผล | บังคับ reason เก็บ version เดิมและ audit | PATCH notes/{id} |
| AI retry | Guest/รอบจบกดเปลี่ยน mock ได้ | จำกัดเฉพาะเจ้าของรอบที่ยังแก้ไขได้ | POST analyses/{id}/retry |

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
| Security/ownership | ตรวจ flow ฝั่ง client เท่านั้น localStorage แก้ได้ | SOC-003, SOC-010 |
| Retention/audit | ไม่มี purge ตาม expires_at; audit ไม่ใช่ server append-only | SOC-010, SOC-016 |
| Experiment | แสดง Not measured; ยังไม่มี A/B/C experiment execution หรือ provider usage จริง | SOC-014 |
| Instructor | มี account/quota/review/comments; ยังไม่ใช่ admin REST หรือ ground-truth access audit ฝั่ง server | SOC-015 |

ข้อจำกัดเหล่านี้ไม่ใช่ข้อยกเว้นสำหรับระบบจริง ต้องทำให้ครบและผ่าน integration/E2E tests ก่อนนับ phase นั้นเสร็จ

## วิธีตรวจ flow ใหม่

1. Login Analyst → เริ่ม S02 → อย่า logout เพื่อพักรอบ ต้องใช้ปุ่มพักโดยตรง
2. เปิด Event explorer กรอง asset/IP/from/to แล้วลองช่วงเวลาที่ from >= to ต้องถูกปฏิเสธ
3. เปิด Ticket ตอนยังมี event ใหม่กำลังเข้ามา กรอก draft แล้วรอหลักฐานเพิ่ม บันทึกด้วย version เก่าต้องพบ VERSION_CONFLICT; กดอัปเดตหลักฐาน draft ยังอยู่
4. บันทึก assessment, แก้ Note โดยใส่เหตุผล, ลบ/กู้คืนแล้วตรวจ audit และประวัติคำตอบ
5. กด Export ก่อนจบรอบต้องไม่ดาวน์โหลด
6. Finish → เห็น Completing → Completed; เปิด Ticket แล้วแก้/ลบ/กู้คืนไม่ได้ แต่ดูหลักฐานและผลประเมินได้
7. Instructor เพิ่ม comment ในรอบจบได้ แต่ปรับ status/severity ไม่ได้

การทดสอบอัตโนมัติอยู่ใน `prototype/tests/model.test.cjs` ผลตรวจ browser และข้อจำกัดการตรวจอัปเดตใน [Prototype QA](../prototype/QA.md)
