# Prototype verification

## Learning path / promotion exam regression — 12 ตุลาคม 2026

- Automated model tests ผ่าน **18/18** รวมการปลดล็อกระดับเมื่อผ่านทุกเคส, rubric จำลอง 4 ข้อ และ exam run ที่ใช้ชื่อ/initial severity เป็นกลาง; `node --check app.js`, `node --check model.js` และ `git diff --check` ผ่าน
- Browser: ผู้เรียนใหม่ login แล้วเห็น onboarding; ก่อนเรียนปุ่มข้อสอบปิดอยู่ บทเรียน 5 ขั้นต้องกด Method → Path → Response → บัญชี/IP → เหตุการณ์ต่อเนื่อง จึงจบบทและเปิดข้อสอบได้
- Browser: เริ่มข้อสอบแล้ว Event explorer แสดงเฉพาะหลักฐาน ไม่มีคำใบ้; Ticket ใช้ชื่อ `Unclassified activity`, severity `Unrated` และไม่แสดง mock AI brief ระหว่างตอบ เมื่อส่งคำตอบผิดหลังหลักฐานครบ แสดง feedback หลัง submit และล็อกรอบเพื่อให้สอบใหม่
- ใช้ `http://localhost:4174/` สำหรับรอบทดสอบแยกจาก localStorage ของ `127.0.0.1` ที่ผู้ใช้เปิดอยู่; ผลนี้ยังไม่ใช่ security/anti-cheat test เพราะ fixture และ rubric อยู่ใน JavaScript ฝั่ง browser

---

## Alignment regression — 12 ตุลาคม 2026

อัปเดตตาม `docs/prototype-alignment.md` ผล QA เดิมด้านล่างเป็นประวัติของเวอร์ชันวันที่ 5 ตุลาคม ไม่ใช่หลักฐานยืนยัน backend/API จริง

- Automated model tests: ผ่าน 15/15 รวม Completing lock, immutable evaluation snapshot, clock catch-up, concurrency limit, expected_version conflict, Instructor ไม่เขียนทับ learner answer, UTC daily quota และ from/to filtering
- Syntax check: app.js, model.js และ server.cjs ผ่าน
- Browser บนพอร์ตทดสอบ 4174: กรอง AUTH-01 ได้ 9 events, export ก่อนจบรอบถูกปฏิเสธ, refresh/login กลับมาเห็น Reviewing ที่เวลา 01:15, บันทึก assessment และอ่านประวัติ revision ได้
- Browser: แก้ note ต้องใส่เหตุผล, ลบ/กู้คืน Ticket พร้อมเหตุผลได้, finish แสดง Completing ก่อน Evaluation, Completed ทำให้ assessment disabled และไม่มีปุ่ม Delete
- ตรวจ browser error log หลัง flow ข้างต้น: ไม่พบ error
- ตรวจหน้า Ticket ที่ 375px และ 1440px: document ไม่กว้างเกิน viewport; ภาพหลังปรับ `screenshots/aligned-readonly.jpg`
- Version conflict และ daily reset ตรวจด้วย model tests; ยังไม่ได้ทดสอบ conflict ข้ามหลาย browser เพราะเป็น local mock
- การตรวจชุดนี้ไม่ใช่การรับรอง cursor API, CSRF, database transaction, real provider หรือ worker; ดูข้อจำกัดใน alignment document

---

ตรวจเมื่อ 5 ตุลาคม 2026 ผ่าน Node.js 24 และ Codex in-app browser ที่ `http://127.0.0.1:4173`

## Automated checks

คำสั่ง `node --test tests/*.test.cjs`: ผ่าน 8/8 กรณี

- ไม่ปล่อย event / ticket ก่อนถึงเวลา
- พักรอบแล้วเวลาและหลักฐานไม่เพิ่ม และปล่อยซ้ำไม่สร้าง event ซ้ำ
- AI fixture ไม่อ้างเหตุการณ์ในอนาคต
- 5 สถานการณ์สร้าง 21 events / 5 correlated tickets และจบการปล่อยในสถานะ Review
- ปฏิเสธลำดับสถานะผิดและการ resolve/close ที่ขาดข้อสรุปหรือเหตุผล
- Soft delete ไม่ตัดสถานการณ์ที่ยังไม่สรุปออกจากการประเมิน
- รอบใหม่ไม่มีข้อมูลจากรอบอื่น และแสดง incomplete evidence ตามจริง
- เคสที่สร้างเองไม่แสดงผลวิเคราะห์อัตโนมัติที่ไม่มีอยู่

Syntax check ผ่านสำหรับ `app.js`, `model.js`, `server.cjs`

## Browser checks ที่ทำแล้ว

| Flow | ผลที่สังเกต |
|---|---|
| Guest overview | 21 events / 5 tickets; เปิดเป็นรอบตัวอย่างอ่านอย่างเดียว |
| Login ผิด | แสดงข้อความผิดพลาดและยังอยู่ในฟอร์ม |
| Demo Analyst | เข้าสู่ Simulation lab ได้ |
| สมัครบัญชีตัวอย่าง | สร้าง `qa.learner@demo.test` และได้บทบาท Analyst |
| เริ่ม / พัก / ดำเนินต่อ | เริ่มว่าง ปล่อย event ตามเวลา พักที่ 00:23 แล้วดำเนินต่อได้ |
| Ticket evidence | เปิด request / response ของ S02-EV-003 และแสดง session SES-041 |
| Workflow validation | Open → Closed ถูกปฏิเสธ; Investigating → Resolved → Closed สำเร็จ |
| Notes | เพิ่ม note อ้างอิง event, แสดง `<script>` เป็นข้อความ, แก้เป็น v2, ลบและกู้คืนได้ |
| Tickets | เปิดเองจาก evidence ได้; ลบเคสแบบ soft delete แล้วกู้คืนได้ |
| AI failure | แสดง unavailable โดยยังมีหลักฐาน; retry คืน fixture ได้ |
| Review / Evaluation | ซ่อนผลก่อนจบรอบ; หลังยืนยันแสดงคำตอบถูก 1/1 สำหรับรอบที่ทดสอบ |
| ไม่มีสิทธิ์ | Analyst เข้า Instructor แล้วพบหน้าปฏิเสธสิทธิ์ |
| Instructor | เปิดตรวจรอบของผู้เรียนและเพิ่มความเห็นได้ |
| จัดการบัญชี | ปิด/เปิดบัญชี QA และปรับโควตาเป็น 20 ได้ |
| Persistence | Refresh แล้ว Login ใหม่พบรอบเดิมและ ticket ที่บันทึกไว้ |
| Refresh evidence | อัปเดตหลักฐานโดยยังคงข้อความ draft ในฟอร์ม |
| Session expired | กลับ Guest และแสดง Login modal พร้อมข้อความ session หมดอายุ |
| Quota full | ไม่สร้างรอบใหม่และแสดง modal โควตาเต็ม |
| Empty state | เปิด Event explorer ของรอบที่พักก่อน event แรกได้ |

ตรวจภาพและขนาดหน้า 375px, 768px และ 1440px: ความกว้าง document ไม่เกิน viewport; เมนูมือถือเปิดแล้วเลือกหน้า Simulation lab ได้ ตารางอยู่ใน container ที่เลื่อนภายในได้ ตรวจ error log ของ browser ตอนจบไม่พบรายการ error

ภาพหน้าตัวอย่าง: `screenshots/overview-desktop.jpg`

## ข้อจำกัดการตรวจ

- ไม่ใช่การทดสอบ security ของระบบจริง เพราะไม่มี backend หรือ authentication จริง
- ยังไม่ได้ทดสอบทุก browser, screen reader, multi-tab concurrency หรือ storage quota exhaustion
- Export JSON มี implementation แต่รอบ QA นี้ไม่ได้เปิดตรวจไฟล์ดาวน์โหลดผ่าน browser
- การปรับสถานะ Ticket โดย Instructor ใช้ตัวตรวจ transition เดียวกับ Analyst แต่ยังไม่ได้กดครบทุก transition ผ่านหน้า Instructor
- ผลประเมินในต้นแบบไม่ใช่ precision/recall ของ detector หรือการวัดคุณภาพ AI จริง

บัญชี QA และรอบที่ทดสอบอยู่เฉพาะ localStorage ของ browser ที่ใช้ตรวจ ไม่ได้ฝังลงใน fixture ที่ส่งมอบ ผู้เปิดจาก browser ใหม่จะเห็น Guest demo เริ่มต้น
