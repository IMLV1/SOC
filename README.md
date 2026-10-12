# test
# Sentinel SOC Learning Lab

เว็บต้นแบบสำหรับเรียนรู้การสืบสวนเหตุการณ์ Security Operations Center (SOC) จากข้อมูลจำลอง ผู้เริ่มต้นเรียนวิธีอ่าน request/response ทีละจุด ก่อนทำเคสทดสอบเพื่อเลื่อนระดับ **เริ่มต้น → กลาง → ชำนาญ**

## เปิด prototype ในเครื่อง

ต้องมี Node.js จากโฟลเดอร์ repository:

```bash
cd prototype
node server.cjs
```

เปิด <http://127.0.0.1:4173/> หากพอร์ตถูกใช้ให้รัน `node server.cjs 4174` แล้วเปิดพอร์ตนั้น ดูบัญชีเดโมและรายละเอียด flow ที่ [คู่มือ prototype](prototype/README.md) ทดสอบ logic ด้วย `cd prototype && npm test`

## สถานะโครงการ

`prototype/` เป็น HTML/CSS/JavaScript ที่ใช้ localStorage, ข้อมูลเหตุการณ์จำลอง และ rubric จำลอง ยัง **ไม่มี backend, authentication, database หรือ AI+RAG จริง** ข้อสอบใน prototype ไม่ป้องกันการเปิด source เพื่อดูเฉลย และยังไม่ใช่เว็บไซต์ที่ deploy สาธารณะ

เอกสารสำหรับพัฒนาระบบจริงอยู่ที่ [docs/README.md](docs/README.md) โดย [ข้อกำหนดเส้นทางเรียนรู้](docs/learning-path.md) ระบุ flow บทเรียน/ข้อสอบและสิ่งที่ต้องทำฝั่ง server ส่วน [ขอบเขต SOC](docs/soc-simulation.md) อธิบายภาพรวมและเกณฑ์งานส่ง
