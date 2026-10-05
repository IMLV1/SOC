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
| `analyst@demo.test` | Analyst | `demo1234` |
| `instructor@demo.test` | Admin / Instructor | `demo1234` |

ใช้ปุ่มเลือกบัญชีได้ทันที หรือกรอกฟอร์มเพื่อทดสอบ Login error สร้างบัญชี Analyst เพิ่มด้วยอีเมลลงท้าย `@demo.test` ได้ รหัสเดโมคงที่และไม่ถูกบันทึกใน storage อย่าใช้รหัสผ่านจริง

## Flow ที่ทดลองได้

1. Guest ดูรอบตัวอย่างแบบอ่านอย่างเดียว มี 21 events และ 5 tickets
2. Login เป็น Analyst → Simulation lab → เลือก 1–5 สถานการณ์ → รอบใหม่
3. Events ทยอยเข้าตามนาฬิกา 75 วินาที พักและดำเนินต่อได้ เมื่อครบเวลาเปลี่ยนเป็น Review ให้สืบสวนต่อโดยยังไม่เปิดเฉลย
4. Event explorer ค้นชื่อ IP บัญชี อุปกรณ์ รหัส event หรือเวลาที่แสดง เช่น `21:00:05` และกรองแหล่ง log (ต้นแบบยังไม่มีตัวเลือกช่วงเวลาจาก–ถึง)
5. Alert queue เชื่อม event กับ ticket เปิด request / response ได้
6. Ticket มีคำวิเคราะห์ AI ตัวอย่างที่อ้างเฉพาะ event ที่ปล่อยแล้ว และ evidence timeline กด “อัปเดตหลักฐาน” เพื่อดึง event ล่าสุดโดยรักษาข้อความในแบบฟอร์มที่กำลังกรอก
7. สร้าง/อ่าน/แก้/ลบแบบ soft delete/กู้คืน ticket และ note ได้ พร้อม audit และประวัติเวอร์ชัน note
8. ประเมินตามลำดับ `Open → Investigating → Resolved → Closed` หรือเปิดกลับจาก Closed เป็น Investigating ต้องมีเหตุผล และต้องมี disposition ก่อน resolve/close
9. จบรอบ → Evaluation แสดงเฉลยเทียบคำตอบของผู้ฝึก โดยไม่ตัด ticket ที่ลบออกจากผล
10. Export เป็น JSON เพื่อเก็บหลักฐาน ticket และ audit ของรอบ
11. Instructor ปิด/เปิดบัญชีตัวอย่าง ปรับโควตา ตรวจรอบ เพิ่มความเห็น และปรับ severity/status พร้อมเหตุผล โดยไม่เขียนทับข้อสรุปของผู้เรียน

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
- Session อยู่ในหน่วยความจำ Refresh แล้วต้อง Login ใหม่ และรอบที่กำลังทำงานจะถูกพัก ไม่สร้างเหตุการณ์ย้อนหลังขณะปิดหน้า
- กฎและ anomaly เป็นผลตรวจจับตาม fixture ไม่ใช่ engine สำหรับตรวจ log จริง
- ไม่มีการวัด Precision/Recall หรือ A/B/C จริง หน้า Evaluation ระบุ Not measured เพื่อไม่สร้างผลทดลองเทียม
- เฉลยอยู่ใน `model.js` ฝั่ง browser จึงป้องกันการอ่านล่วงหน้าทางเทคนิคไม่ได้ แม้ UI จะซ่อนก่อนจบรอบ
- Audit เป็นข้อมูล local ที่แก้ไม่ได้ผ่าน UI แต่ไม่ได้ป้องกันการแก้จาก developer tools
- ไม่มีการโจมตีจริงหรือ response action; ต้นแบบใช้ workflow ล่าสุดในเอกสารที่ไม่มี Contained
- ยังไม่รองรับ retention policy, server-enforced quota, ส่งอีเมล หรือ public deployment

## โครงสร้างไฟล์

```text
prototype/
  index.html           จุดเริ่มต้น
  styles.css           ธีมและ responsive layout
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
