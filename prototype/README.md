# Sentinel — SOC Simulation Prototype

เว็บต้นแบบตาม `../docs/soc-simulation.md` ฉบับ AI-Assisted SOC Simulation Platform ใช้ HTML, CSS และ JavaScript ไม่ต้องติดตั้ง dependencies

## วิธีเปิด

รันจากโฟลเดอร์ `prototype`:

```powershell
node server.cjs
```

เปิด <http://127.0.0.1:4173> หรือเปิด `index.html` โดยตรงเพื่อดูต้นแบบ (แนะนำ local server เพื่อให้ localStorage ทำงานสม่ำเสมอ)

เซิร์ฟเวอร์ผูกเฉพาะ loopback สำหรับดูบนเครื่องนี้ ยังไม่ได้ publish สู่สาธารณะ ฟอนต์ Google Fonts เป็นส่วนเสริม หากออฟไลน์จะใช้ฟอนต์ของเครื่อง

## บัญชีตัวอย่าง

| บัญชี | บทบาท | รหัสเดโม |
|---|---|---|
| `analyst@demo.test` | Analyst | `DemoSOC1234!` |
| `instructor@demo.test` | Admin / Instructor | `DemoSOC1234!` |

ใช้ปุ่มเลือกบัญชีได้ทันที หรือกรอกฟอร์มเพื่อทดสอบ Login error สร้างบัญชี Analyst เพิ่มด้วยอีเมลลงท้าย `@demo.test` ได้ รหัสเดโมคงที่และไม่ถูกบันทึกใน storage อย่าใช้รหัสผ่านจริง

## Flow ที่ทดลองได้

1. หน้าแรกเป็นเส้นทางเรียนรู้ 3 ระดับ Guest ดูแผนการเรียนได้ และเปิด Overview เพื่อดูรอบตัวอย่างแบบอ่านอย่างเดียว (21 events, 5 tickets)
2. Login เป็น Analyst → ระบบแนะนำเส้นทาง → เปิดบทเรียนของระดับที่ปลดล็อก
3. บทเรียนแต่ละระดับสอนอ่าน Request/Response แบบกดดูทีละจุด 5 ขั้น: Method, Path, Response status, บัญชี/IP และเหตุการณ์ต่อเนื่อง พร้อมอธิบายว่าแต่ละจุดบอกอะไรและยังสรุปอะไรไม่ได้ เมื่อเรียนครบจึงเปิดเคสทดสอบ
4. ทดสอบระดับเริ่มต้น (S01, S03) → ระดับกลาง (S04, S02) → ชำนาญ (S05) ผ่านทุกเคสทดสอบในระดับก่อนจึงเปิดบทเรียนระดับถัดไป แต่ละรอบเลือกหนึ่งเคส
5. Events ทยอยเข้าตามนาฬิกา 75 วินาที พักและดำเนินต่อได้ เมื่อครบเวลาเปลี่ยนเป็น Reviewing ให้สืบสวนต่อโดยยังไม่เปิดเฉลย
6. Event explorer ค้นข้อความ กรอง source/asset/user/IP และช่วงเวลา ISO UTC (from รวม, to ไม่รวม) ได้ มี pagination ครั้งละ 10 events ช่วงทดสอบไม่แสดงคำใบ้
7. Alert queue เชื่อม event กับ ticket เปิด request / response ได้
8. Ticket มี evidence timeline และแบบฟอร์มคำตอบ ช่วงทดสอบซ่อนคำวิเคราะห์ mock AI กับคู่มือประกอบ กด “อัปเดตหลักฐาน” เพื่อดึง event ล่าสุดโดยรักษาข้อความในแบบฟอร์ม
9. ช่วงทดสอบผู้เรียนต้องเลือก event ที่ชี้ขาด, disposition, severity และเขียนเหตุผลเอง หลังส่งจึงเห็นผล rubric จำลอง 4 ด้าน หากส่งก่อนหลักฐานครบให้รอแล้วส่งใหม่; หากหลักฐานครบแต่ไม่ผ่าน รอบจะจบและเริ่มทดสอบใหม่ได้
10. สร้าง/อ่าน/แก้/ลบแบบ soft delete/กู้คืน ticket และ note ได้ พร้อม audit และประวัติเวอร์ชัน note
11. ประเมินตามลำดับ `Open → Investigating → Resolved → Closed` หรือเปิดกลับจาก Closed เป็น Investigating ต้องมีเหตุผล และต้องมี disposition ก่อน resolve/close
12. จบรอบ → Completing (mock pending) → Completed ล็อกคำตอบและ snapshot ก่อนเปิดเฉลย รายการที่ลบยังอยู่ในการประเมิน หลังจบรอบแก้ไข/ลบ/กู้คืน ticket หรือ note ไม่ได้ แต่ Instructor เพิ่ม comment ได้
13. Export เป็น JSON หลัง Completed เท่านั้น เก็บหลักฐาน ticket audit และ evaluation snapshot
14. Instructor ปิด/เปิดบัญชีตัวอย่าง ปรับโควตา ตรวจรอบ เพิ่มความเห็น และปรับ severity/status พร้อมเหตุผล โดยไม่เขียนทับข้อสรุปของผู้เรียน

## สถานะพิเศษสำหรับสาธิต

ปุ่ม sliders มุมขวาบน (Prototype test states) รองรับ:

- AI unavailable และ retry โหลด fixture ใหม่ โดยไม่บล็อกการตรวจหลักฐาน
- โควตาเต็ม พร้อมทางกลับไปดู ticket เดิม
- Session หมดอายุและ Login ใหม่ โดยเก็บประวัติรอบไว้
- Empty state: เริ่มรอบใหม่และพักก่อนปล่อย event แรก
- Access denied: เข้า Instructor ด้วย Analyst หรือ Guest

Validation ทดลองได้ด้วยการ Login ผิด ข้ามลำดับสถานะ หรือ resolve โดยไม่เลือกข้อสรุป การลบต้องยืนยันพร้อมเหตุผล

## ขอบเขตของต้นแบบ

- ไม่มี backend API, ฐานข้อมูล, authentication จริง หรือ AI provider
- Login และการแยกข้อมูลตามบัญชีเป็นการสาธิต UI เท่านั้น ผู้ที่เข้าถึง browser สามารถอ่านหรือแก้ข้อมูลทั้งหมดได้
- เก็บรอบและชื่อบัญชีตัวอย่างใน localStorage ของ browser นี้ ไม่ซิงค์ข้ามเครื่องหรือ browser
- Session อยู่ในหน่วยความจำ Refresh แล้วต้อง Login ใหม่ แต่ logout ไม่พักรอบ ใช้เวลาที่บันทึกไว้ทำ wall-clock catch-up เมื่อเปิดหน้าใหม่; เป็นการจำลองพฤติกรรม server clock เท่านั้น ไม่ใช่ worker จริง และยังไม่รองรับ multi-tab concurrency
- กฎและ anomaly เป็นผลตรวจจับตาม fixture ไม่ใช่ engine สำหรับตรวจ log จริง
- ตัวช่วยสอนที่เรียก AI/RAG coach ใน UI เป็นคู่มือข้อความและ rubric ที่เตรียมไว้ ไม่ได้เรียก LLM หรือค้น knowledge base จริง และตรวจความหมายของเหตุผลแบบอิสระไม่ได้
- การทดสอบเลื่อนขั้นใน prototype ซ่อนคำใบ้และคะแนนตั้งต้นในหน้าทดสอบ แต่ยังใช้ fixture ที่อยู่ฝั่ง browser เดียวกับรอบตัวอย่าง ผู้ใช้ที่เปิด developer tools หรือทบทวน demo อาจเห็นคำตอบได้ ระบบจริงต้องแยกโจทย์ทดสอบจากตัวอย่าง เก็บเฉลยและตรวจคำตอบฝั่ง backend
- ความก้าวหน้าเก็บจากผลผ่านที่บันทึกในรอบของบัญชีตัวอย่างบน browser นี้ ไม่ซิงค์ข้ามอุปกรณ์
- ไม่มีการวัด Precision/Recall หรือ A/B/C จริง หน้า Evaluation ระบุ Not measured เพื่อไม่สร้างผลทดลองเทียม
- เฉลยอยู่ใน `model.js` ฝั่ง browser จึงป้องกันการอ่านล่วงหน้าทางเทคนิคไม่ได้ แม้ UI จะซ่อนก่อนจบรอบ
- Audit เป็นข้อมูล local ที่แก้ไม่ได้ผ่าน UI แต่ไม่ได้ป้องกันการแก้จาก developer tools
- ไม่มีการโจมตีจริงหรือ response action; ต้นแบบใช้ workflow ล่าสุดในเอกสารที่ไม่มี Contained
- จำลองโควตารายวัน UTC และหนึ่ง running run ต่อบัญชีแล้ว แต่ยังไม่มี retention policy, server-enforced quota, อีเมล หรือ public deployment

## โครงสร้างไฟล์

```text
prototype/
  index.html           จุดเริ่มต้น
  styles.css           ธีมและ responsive layout
  learning.css         หน้าระดับและคำแนะนำสำหรับผู้เริ่มต้น
  model.js             fixtures, clock, evidence, ticket transitions, evaluation
  app.js               หน้าจอและ interactions
  server.cjs           local static server (Node built-in modules)
  tests/model.test.cjs  tests สำหรับเงื่อนไขสำคัญของการฝึก
  QA.md                ผลตรวจและรายการตรวจด้วยมือ
```

## ทดสอบ

```powershell
node --test tests/*.test.cjs
```

รองรับหน้าจอ 375px, 768px และ 1440px ตารางเลื่อนภายใน panel ได้ บนมือถือใช้เมนูพับและ layout คอลัมน์เดียว

## Alignment update — 12 ตุลาคม 2026

อ่าน [ตารางเทียบ prototype กับ architecture/API](../docs/prototype-alignment.md) สำหรับสิ่งที่ทำแล้วและขอบเขต mock ที่ยังไม่ใช่ backend จริง

- สมัครบัญชีแล้วกลับหน้า Login ไม่เข้าสู่ระบบอัตโนมัติ
- รหัสเดโมปัจจุบันคือ `DemoSOC1234!` (12 ตัวอักษร) ใช้เฉพาะการสาธิต ไม่เก็บ password และยังไม่ใช่ registration จริง
- กู้คืน Ticket/Note และแก้ Note ต้องใส่เหตุผล มี version check และประวัติคำตอบของผู้ฝึก
- assessment ที่ใช้ version เก่าถูกปฏิเสธ โดยเก็บ draft และกดอัปเดตหลักฐานเพื่อโหลด version ล่าสุด
- เมื่อพอร์ตเดิมถูกใช้ เปิดพอร์ตอื่นได้ด้วย `node server.cjs 4174`
