# SOC documentation

เอกสารสำหรับพัฒนาจาก prototype ไปเป็นระบบจริง อัปเดตแผนวันที่ 12 ตุลาคม 2026

Stack ที่เลือก: **Next.js + TypeScript · FastAPI + Python · PostgreSQL** พร้อม Python worker, SQLAlchemy/asyncpg และ Alembic; CI/CD ใช้ GitHub Actions ตามแบบออกแบบ

| เอกสาร | ใช้อ่านเรื่อง |
|---|---|
| [soc-simulation.md](soc-simulation.md) | แนวคิด ขอบเขต สถานการณ์และเกณฑ์งานรายวิชา |
| [architecture.md](architecture.md) | Stack ที่เสนอ โครงสร้างระบบ ข้อมูล queue/worker AI และ deployment |
| [api.md](api.md) | Endpoint, authentication, request/response, validation และสิทธิ์ |
| [database.md](database.md) | ER diagram, ตาราง/ความสัมพันธ์, constraints, transactions, DB roles, migrations และ backup |
| [ci-cd.md](ci-cd.md) | GitHub Actions, checks/tests/build, Docker artifacts, staging/production deploy และ rollback |
| [rag-langchain.md](rag-langchain.md) | LangChain RAG, pgvector, knowledge ingestion, Ask AI, citations, สิทธิ์และการวัดคุณภาพ |
| [development-plan.md](development-plan.md) | Roadmap, backlog, dependencies และ acceptance tests |
| [Prototype guide](../prototype/README.md) | วิธีเปิดต้นแบบและขอบเขตที่ยังเป็น mock |
| [Prototype alignment](prototype-alignment.md) | เทียบพฤติกรรมต้นแบบกับ architecture/API และแยกงานที่ยังรอ backend |

แนะนำให้อ่าน scope → architecture → API/database → CI/CD → development plan ก่อนเริ่ม implementation

Architecture และ API เป็นข้อเสนอ ยังไม่ได้ติดตั้ง backend/ฐานข้อมูล/provider จริง ขั้นถัดไปตามแผนคือจัดทำ SRS และ OpenAPI ที่ตรวจด้วยเครื่องมือได้ แล้วเริ่ม vertical slice ของ login → run → events
