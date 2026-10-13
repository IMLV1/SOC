# ผลตรวจข้อ 02 — 13 ตุลาคม 2026

สถานะ: **ผ่านขอบเขตข้อ 02** รวม Compose execution บน Linux engine จริง
คง branch f1; ก่อนแก้ working tree สะอาด และ fast-forward จาก 65d5562 ไป remote f1 3c952c9
เพื่อรับ README/.gitkeep changes เดิม ไม่แตะ main/prototype และไม่ commit/push/deploy ในงานนี้
ไม่พบ AGENTS.md ใน repository และ parent ที่ตรวจ

## ไฟล์และขอบเขต

- compose.yaml, backend/frontend Dockerfiles และ .dockerignore: DB → bootstrap → migrate → API/worker/web;
  named volume และ test-db tmpfs แยก; pin image versions/digests จาก official registry
- scripts/init-local.py, .env.example, backend/.env.example, .gitignore: สร้าง role passwords สุ่ม
  ไว้เฉพาะ .local; mount แยก credential แต่ละ process ไม่มี default Instructor password
- backend/app/db: config, SQLAlchemy async sessions, privileged bootstrap,
  migration wrapper/ledger/lock, readiness และ provisioning/assignment CLI
- backend/alembic.ini, migrations: initial auth schema 7 app tables + 2 ops tables,
  grants/indexes/constraints; private schema ว่าง; ไม่มี runs/jobs/exam/RAG tables
- app/main.py, app/worker: DB-backed health; worker foundation loop/check ไม่มี queue jobs
- pyproject.toml/uv.lock: SQLAlchemy asyncio extra และ Argon2-cffi 25.1.0
- test_database.py/test_foundation.py, frontend smoke: real DB grants/transactions และ health contract
- docs/openapi.yaml: เปลี่ยนเฉพาะ approved health readiness เป็น 200/503 พร้อม safe models;
  domain inventory 79 operations ยัง draft เช่นเดิม
- frontend landing: บอกสถานะข้อ 02 และเพิ่มลิงก์ readiness; ไม่สร้าง feature auth/exam

## หลักฐานที่รันจริง

| Check | ผล |
|---|---|
| Native DB | EDB PostgreSQL 17.11 Windows binaries; cluster ใน .local/pg-test-data, localhost:55439 เท่านั้น ไม่ติดตั้ง system service |
| Fresh migration | ผ่านบนฐาน soc_test_step02; initial DDL failure rollback ทุกตาราง แล้ว retry สำเร็จ |
| Repeat/concurrent/lock | ผ่าน; advisory lock เดียวกัน, checksum ledger หนึ่ง revision, ไม่ซ้ำเมื่อ migrate พร้อมกัน |
| Drift guard | checksum mismatch ปฏิเสธ migration และ readiness; approved OpenAPI drift tests ผ่าน |
| Runtime permissions | ทดสอบด้วย api/worker/evaluator/retention จริง: ไม่ใช่ owner/superuser, DDL/private/ledger mutation/SET ROLE owner ถูกปฏิเสธ |
| Audit | api/worker/evaluator insert ได้; update/delete/truncate ถูกปฏิเสธ |
| Provisioning | concurrent/repeat ได้ UUID เดียว, mismatch ไม่ทับบัญชี, Argon2 verify ผ่าน, assignment ไม่ซ้ำ/สลับ role ไม่ได้ |
| CLI | สร้าง Instructor ด้วย private random password file สองครั้ง คืน UUID เดียว ไม่มี password ใน output |
| Constraints/session transaction | email/token unique, FK, role/version, nonnegative quota, scope binding, raw token rejection และ rollback ผ่าน |
| Backend suite | 29 passed = 16 PostgreSQL integration + 13 foundation; 1 upstream HTTPX test-client deprecation warning |
| Static/dependencies | Ruff app/tests/migrations/scripts, mypy app และ uv sync --frozen --offline ผ่าน; git diff --check ผ่าน |
| Readiness | API ใช้ api_runtime, worker ใช้ worker_runtime; DB/head/checksums ถูกให้ ready; credential ไม่ตรงปฏิเสธ |
| Restart persistence | หยุด/เริ่ม PostgreSQL จริง; user IDs, session/challenge counts, migration revisions snapshot ตรงเดิม |
| Failure/recovery smoke | ระหว่าง DB หยุด API readiness 503; หลัง restart frontend proxy readiness 200 |
| Frontend | ESLint/typecheck/production build ผ่าน; HTTP smoke 3 passed กับ API+PostgreSQL จริง |
| Worker process | เริ่มและรายงาน database_ready=true, queue_ready=false; ไม่มี runner/job handlers |
| Compose | Docker Desktop 4.95.0, Engine 29.8.2 linux/amd64, Compose 5.6.0; config/build/up --wait ผ่านบน named volume ใหม่ |
| Docker images | pinned Python/Node/PostgreSQL images pull/build/run ผ่าน; API/worker UID 10001 และ frontend UID 1000 ไม่ใช่ root |
| Container integration | test profile: 16 passed, 1 upstream warning; test-db เป็น tmpfs แยกจาก soc named volume |
| Container frontend | HTTP smoke 3 passed ที่ localhost:3000; assets/proxy/readiness และ draft route 404 ผ่าน |
| Container provisioning | private random password file mount read-only; รันซ้ำได้ UUID เดิม ไม่พิมพ์ password |
| Container persistence | หยุด DB แล้ว readiness 503; down/up โดยไม่ลบ volume แล้ว user UUID/email/role, migration checksum และ audit count ตรงเดิม; readiness กลับ 200 |
| Final services | db/api/worker/frontend healthy; bootstrap/migrate exit 0; หยุด test-db หลังทดสอบ |

Frontend build ครั้งแรกติด EBUSY เพราะ standalone server จากข้อ 01 ถือ directory อยู่
หยุดเฉพาะ process ที่เปิดไว้ใน chat นี้แล้ว build ผ่าน ไม่ลบงานผู้ใช้หรือแก้ test ให้ผ่านผิด ๆ
เริ่ม native API/UI สำหรับ smoke ที่ 8002/3002 เพื่อเลี่ยง service เดิม ส่วน Compose ใช้ 8000/3000

## ประวัติ blocker และผลตรวจต่อ

รอบแรก `docker compose build` ล้มเพราะไม่มี Docker daemon pipe (`docker_engine` not found)
เมื่อกลับมาทำต่อ พบ Docker Desktop ติดตั้งแล้วและ engine พร้อม จึงไม่ได้ติดตั้งซ้ำ
ตรวจ Linux build, secret mounts ภายใต้ non-root users, startup บน volume ใหม่,
integration/provisioning และ named-volume persistence ผ่านครบแล้ว คำสั่งสำหรับรันซ้ำ:

```powershell
python scripts/init-local.py
docker compose up --build -d
docker compose ps -a
docker compose --profile test run --build --rm test
docker compose restart db
# ตรวจ readiness และข้อมูลบัญชีที่ provision ยังอยู่
```

ใช้ [คู่มือ](local-development.md) สำหรับ ports/provisioning/test isolation และ shutdown
ยังไม่มี auth UI/API, CI (ข้อ 03), durable jobs/heartbeat/runner (ข้อ 06), pgvector,
provider/exam/grading/deployment/backup. ไม่เลือก rubric/override/retake policy เพิ่ม
PostgreSQL 17 เป็น local baseline; production hosting และ major/extension compatibility ยัง pending
รายงานข้อ 01 เป็นประวัติผลเดิม ส่วน readiness/worker ปัจจุบันใช้พฤติกรรมข้อ 02
