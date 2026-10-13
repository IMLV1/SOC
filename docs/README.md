# SOC documentation

เอกสารสำหรับพัฒนาจาก prototype ไปเป็นระบบจริง อัปเดตแผนวันที่ 12 ตุลาคม 2026

Stack ที่เลือก: **Next.js + TypeScript · FastAPI + Python · PostgreSQL** พร้อม Python worker, SQLAlchemy/asyncpg และ Alembic; CI/CD ใช้ GitHub Actions ตามแบบออกแบบ

| เอกสาร | ใช้อ่านเรื่อง |
|---|---|
| [soc-simulation.md](soc-simulation.md) | แนวคิด ขอบเขต สถานการณ์และเกณฑ์งานรายวิชา |
| [learning-path.md](learning-path.md) | บทเรียนสำหรับผู้เริ่มต้น ข้อสอบเลื่อนระดับ การตรวจคำตอบ AI+RAG และเกณฑ์รับงาน |
| [architecture.md](architecture.md) | Stack ที่เสนอ โครงสร้างระบบ ข้อมูล queue/worker AI และ deployment |
| [api.md](api.md) | Endpoint, authentication, request/response, validation และสิทธิ์ |
| [database.md](database.md) | ER diagram, ตาราง/ความสัมพันธ์, constraints, transactions, DB roles, migrations และ backup |
| [ci-cd.md](ci-cd.md) | GitHub Actions, checks/tests/build, Docker artifacts, staging/production deploy และ rollback |
| [rag-langchain.md](rag-langchain.md) | LangChain RAG, pgvector, knowledge ingestion, Ask AI, citations, สิทธิ์และการวัดคุณภาพ |
| [development-plan.md](development-plan.md) | Roadmap, backlog, dependencies และ acceptance tests |
| [implementation-checklist.md](implementation-checklist.md) | ลำดับเขียนโค้ด 19 ช่วง พร้อม prompt และเกณฑ์ตรวจรับแต่ละช่วง |
| [srs.md](srs.md) | SRS เริ่มต้น, contract gaps, exam boundary/lifecycle/locks และ requirement mapping |
| [openapi.yaml](openapi.yaml) | Machine-readable contract; approved health และ draft domain operations |
| [getting-started.md](getting-started.md) | Runtime pins, lockfiles และวิธีเปิด scaffold ในเครื่อง |
| [step-01-verification.md](step-01-verification.md) | ผลตรวจข้อ 01 และข้อจำกัดที่ยังไม่พร้อม |
| [local-development.md](local-development.md) | Compose, PostgreSQL, migration/roles, provisioning และฐานทดสอบแยก |
| [step-02-verification.md](step-02-verification.md) | ผลตรวจฐานข้อมูลจริง และส่วน Compose ที่ยังรอ Docker engine |
| [Prototype guide](../prototype/README.md) | วิธีเปิดต้นแบบและขอบเขตที่ยังเป็น mock |
| [Prototype alignment](prototype-alignment.md) | เทียบพฤติกรรมต้นแบบกับ architecture/API และแยกงานที่ยังรอ backend |

แนะนำให้อ่าน scope → learning path → architecture → API/database → CI/CD → development plan ก่อนเริ่ม implementation

มี scaffold frontend/API health และ worker entrypoint จากข้อ 01 แล้ว พร้อม SRS/OpenAPI เริ่มต้น
ข้อ 02 มี database foundation/migration/roles แล้ว; domain APIs, authentication และ provider ยังไม่ implement
Compose build/up, integration tests และ named-volume persistence ผ่านแล้ว
ข้อ 03 เพิ่ม CI/local checks แล้ว ดู [คู่มือ](ci-local.md) และ [ผลตรวจ](step-03-verification.md)
GitHub CI ข้อ 03 ผ่านแล้ว แต่ required check/branch protection ติดข้อจำกัดแพ็กเกจ private repository
ข้อ 04 เพิ่ม auth/me และ Guest snapshot ดู [คู่มือ](auth-development.md) และ [ผลตรวจ](step-04-verification.md)
