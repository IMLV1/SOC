# SOC documentation

เอกสารสำหรับพัฒนาจาก prototype ไปเป็นระบบจริง อัปเดตแผนวันที่ 12 ตุลาคม 2026

| เอกสาร | ใช้อ่านเรื่อง |
|---|---|
| [soc-simulation.md](soc-simulation.md) | แนวคิด ขอบเขต สถานการณ์และเกณฑ์งานรายวิชา |
| [architecture.md](architecture.md) | Stack ที่เสนอ โครงสร้างระบบ ข้อมูล queue/worker AI และ deployment |
| [api.md](api.md) | Endpoint, authentication, request/response, validation และสิทธิ์ |
| [development-plan.md](development-plan.md) | Roadmap, backlog, dependencies และ acceptance tests |
| [Prototype guide](../prototype/README.md) | วิธีเปิดต้นแบบและขอบเขตที่ยังเป็น mock |
| [Prototype alignment](prototype-alignment.md) | เทียบพฤติกรรมต้นแบบกับ architecture/API และแยกงานที่ยังรอ backend |

แนะนำให้อ่าน scope → architecture → API → development plan ก่อนเริ่ม implementation

Architecture และ API เป็นข้อเสนอ ยังไม่ได้ติดตั้ง backend/ฐานข้อมูล/provider จริง ขั้นถัดไปตามแผนคือจัดทำ SRS และ OpenAPI ที่ตรวจด้วยเครื่องมือได้ แล้วเริ่ม vertical slice ของ login → run → events
