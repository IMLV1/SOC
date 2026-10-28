# Sentinel SOC Learning Lab

โครงการนี้เป็นเว็บฝึกอ่านและสืบสวนเหตุการณ์ SOC ด้วยข้อมูลจำลอง ผู้เรียนดูหลักฐาน เช่น HTTP request, response และ log แล้วฝึกอธิบายว่าเกิดอะไรขึ้น หลักฐานใดรองรับข้อสรุป และยังสรุปอะไรไม่ได้

## สถานะปัจจุบัน

คู่มือส่งงานล่าสุด: [ระบบ/Flow/ER](docs/current-system.md) · [วิธีเล่นและนำเสนอ](docs/presentation-guide.md) · [สิ่งที่ยังขาดตาม Deliverables](docs/presentation-readiness.md)

ให้เพื่อนทดลอง: [ส่งอะไรให้เพื่อน / วิธี clone และเปิด local stack](docs/friend-testing.md)

ระบบมีทั้ง prototype และเว็บแอปที่พัฒนาแยกกัน เว็บแอปใช้ Next.js, FastAPI และ PostgreSQL มีระบบบัญชี บทเรียน รอบฝึก ตัวตรวจจับ Ticket การวิเคราะห์ และข้อสอบที่ Instructor ตรวจได้. Local Supabase stack ของผู้พัฒนาเปิด Dify lesson Tutor แล้วเมื่อ 28 ต.ค. 2026 แต่ checkout ใหม่ยังไม่เปิด real AI อัตโนมัติ; investigation provider ยังใช้ mock

## ขอบเขต RAG ที่ต้องเข้าใจให้ตรงกัน

ทิศทางผลิตภัณฑ์ที่ผู้ใช้ยืนยันคือใช้บริการ RAG ภายนอก โดยระบุ Dify และให้ repository เรียกบริการผ่าน API เท่านั้น ไม่ควรอธิบายว่าทีมสร้างระบบ RAG เอง

Source ยังเก็บ pipeline ภายในและ Gemini adapter เดิมเพื่ออ้างอิง; ปิดเส้นทาง Gemini ใน runtime ปัจจุบันแล้ว. ผู้ช่วยสอนในหน้าบทเรียนเชื่อม Dify Workflow ผ่าน server/worker และเก็บประวัติใน DB โดยตรวจ release/citations/budget ตาม [ผลตรวจล่าสุด](docs/dify-integration-verification.md) ไม่ใช่ AI grading หรือการยืนยัน public deployment

การทดสอบในเครื่องไม่ได้แปลว่าเปิดใช้บน staging หรือ production แล้ว ข้อ 14 ยังรอการตรวจคุณภาพและการกระทบยอดการเรียก provider ที่ไม่ทราบผล 6 ครั้ง ส่วนข้อ 18–19 ยังขาดหลักฐาน staging, rollback และ backup/restore ดู [รายการงานและสถานะ](docs/implementation-checklist.md)

## เริ่มดูได้สองแบบ

### เปิด prototype

Prototype ใช้ HTML/CSS/JavaScript และข้อมูลตัวอย่างใน browser ไม่ต้องมีฐานข้อมูลหรือบัญชีจริง:

```bash
cd prototype
node server.cjs
```

จากนั้นเปิด <http://127.0.0.1:4173/> วิธีใช้และข้อจำกัดอยู่ใน [คู่มือ prototype](prototype/README.md)

### เปิดระบบที่เชื่อม API และฐานข้อมูล

ต้องมี Docker Desktop ทำงานอยู่ก่อน จากโฟลเดอร์ repository ให้ทำตาม [คู่มือ local development](docs/local-development.md) คู่มือนี้แยกขั้นตอนสร้างฐานข้อมูล เริ่มเว็บ และรัน migration ไว้แล้ว อย่าใช้คำสั่งทดสอบที่ลบ volume กับฐานข้อมูลที่ต้องการเก็บ

## อ่านเอกสาร

เริ่มจาก [สารบัญเอกสาร](docs/README.md) ถ้าต้องการรู้ว่าทำอะไรแล้ว ให้ดู [implementation checklist](docs/implementation-checklist.md) และรายงานตรวจของข้อนั้น รายงานแต่ละฉบับระบุวันที่ สาขา/commit และสภาพแวดล้อมที่ทดสอบไว้

`prototype/` เป็นตัวอย่าง flow เท่านั้น ไม่ใช่ backend ของเว็บแอป ใช้ localStorage และข้อมูลจำลอง จึงห้ามใช้เป็นหลักฐานว่าระบบบัญชี ข้อสอบ คะแนน หรือ RAG จริงปลอดภัยและทำงานครบแล้ว
