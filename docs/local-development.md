# Local database environment — ข้อ 02

Implementation, native PostgreSQL และ Docker build/up/integration/persistence ผ่านแล้ว
ดู [ผลตรวจ](step-02-verification.md) ขอบเขตนี้เป็น local foundation ยังไม่มี domain features

## ขอบเขตและสิทธิ์

PostgreSQL 17.11, SQLAlchemy async/asyncpg, Alembic one-shot, roles/grants,
readiness, provisioning CLI และ Compose สำหรับ API/worker/Next.js
ข้อ 04 เพิ่ม auth routes และ auth_rate_limits แล้ว ดู [คู่มือ auth](auth-development.md)
ข้อ 05 เพิ่ม training catalog/private truth และ seed one-shot ดู [คู่มือ](scenario-development.md)
ข้อ 06–10 เพิ่ม runner/detection/investigation/analysis; exam และ RAG ยังไม่เปิด
ตารางด้านล่างอธิบาย database foundation ตอนข้อ 02
quota limits ต้องระบุโดย operator ไม่กำหนด default policy ของผลิตภัณฑ์แทนผู้ใช้

| ส่วน | สิ่งที่มี |
|---|---|
| app | users, auth_sessions, auth_challenges, user_quotas, quota_ledgers, instructor_assignments, audit_logs |
| ops | alembic_version, schema_migrations: checksum/applied_at/release_sha |
| private | schema ว่าง ไม่มีเฉลย/fixture |
| migration_owner | schema/table owner สำหรับ DDL/seed/grants; ไม่ใช่ superuser/createdb/createrole |
| api_runtime | auth/users/quotas ตาม needs, assignment SELECT, audit SELECT/INSERT; ไม่มี DDL/private/แก้หรือลบ audit |
| worker_runtime/evaluator_runtime | ops SELECT, app USAGE, audit INSERT; ไม่มี user password/private access ในขั้นนี้ |
| retention_runtime | ops SELECT; auth_sessions/auth_challenges/audit SELECT/DELETE สำหรับ retention; ไม่ใช่บัญชีใช้งานทั่วไป |

runtime ไม่เป็น owner และ SET ROLE migration_owner ไม่ได้ ยังไม่อ้างว่ามี RLS;
HTTP ownership/assignment checks อยู่ข้อ 04 ส่วน audit.run_id/FK รอ runs ในข้อ 06
evaluator private grants จะเพิ่มเฉพาะตารางที่จำเป็นเมื่อมี evaluator จริง

## เปิดด้วย Compose

ต้องมี Docker Engine/Desktop เปิด Linux containers และ Compose plugin
ตรวจจริงด้วย Docker Desktop 4.95.0, Linux Engine 29.8.2 และ Compose 5.6.0
จาก root ใช้ Python ตาม runtime pin เดิม:

```powershell
python scripts/init-local.py
docker compose config --quiet
docker compose up --build -d
docker compose ps -a
docker compose logs bootstrap migrate
```

init-local สร้างรหัสผ่านสุ่มแยกแต่ละ DB role ใน `.local/secrets` ที่ gitignore
รันซ้ำไม่เปลี่ยน/พิมพ์รหัสเดิม ไม่มี seeded Instructor password หรือ demo accounts อัตโนมัติ
POSIX ใช้ `.local` 0700; ไฟล์ภายใน read-only และอ่านได้เมื่อ mount ให้ container user
Windows ใช้ ACL ของโฟลเดอร์ผู้ใช้ เก็บ `.local` ส่วนตัว ไม่อัปโหลดเป็น artifact
อย่าลบ/สร้าง secrets ใหม่เมื่อมี volume เก่าโดยคาดว่ารหัส postgres ใน volume จะเปลี่ยนเอง

ลำดับปัจจุบัน: db healthy → bootstrap → migrate exit 0 → seed exit 0 → API/worker/evaluator → frontend
bootstrap/migrate เป็น one-shot; exit 0 คือสำเร็จ ไม่ใช่ service ล่ม
bootstrap เท่านั้นเห็น admin/role secrets; migrate/provision เห็น owner secret;
API เห็นเฉพาะ api_runtime, worker เฉพาะ worker_runtime, evaluator เฉพาะ evaluator_runtime
และ frontend ไม่มี DB secret
ไม่มี migration ใน Uvicorn/worker startup

- [UI](http://127.0.0.1:3000), [API docs](http://127.0.0.1:8000/docs)
- DB จาก host: 127.0.0.1:55432 database soc
- `/health/live`: 200 เมื่อ process ตอบได้ แม้ DB ล่ม
- `/health/ready`: 200 `{data:{status:ready},meta:{request_id}}` เมื่อ role/head/checksums ถูก;
  503 error envelope เมื่อ config/DB/schema ไม่พร้อม ไม่เผย credentials/SQL

เปลี่ยนพอร์ตผ่าน root `.env.example` → `.env`; password ใช้ไฟล์ ไม่ใส่ env
frontend container build ใช้ BACKEND_ORIGIN=http://api:8000 เป็น same-origin proxy
หน้าเริ่มต้นมีลิงก์ readiness และ auth UI ตามคู่มือข้อ 04; run/exam domain UI ยังไม่เปิด

```powershell
docker compose restart db
docker compose ps
docker compose down
docker compose up -d
```

down ปกติคง named volume; ไม่ใช้ `down -v` เว้นแต่ตั้งใจลบข้อมูล local ทั้งหมด
Dockerfiles นี้เป็น local foundation ยังไม่ใช่ production release/backup/restore

## Gemini Free Tier สำหรับ training จำลองในเครื่อง

ค่าเริ่มต้นเป็น `mock`. เปิด real analysis เฉพาะหลังยืนยัน Free Tier แบบไม่ผูก billing
ใน project ที่เลือก; real run จะ pin provider/model ตอนเริ่ม และ run เก่ายังคง config เดิม
ข้อมูล Free Tier อาจถูกใช้ปรับปรุงบริการ จึงส่งได้เฉพาะ synthetic training fixtures
ห้ามส่ง ground truth, credentials หรือข้อมูลผู้เรียนจริง. Embedding/RAG และ exam ไม่ได้เปิด

สร้าง `.env` จาก template เมื่อไฟล์ยังไม่มี แล้วตั้งค่าต่อไปนี้ใน `.env`:

```dotenv
SOC_AI_PROVIDER=gemini_free
GEMINI_PROJECT_TIER_CONFIRMED=free_no_billing
GEMINI_SYNTHETIC_DATA_ONLY=true
GEMINI_CHAT_MODEL=gemini-3.5-flash-lite
```

เก็บ key แบบไม่ใส่เครื่องหมายคำพูดใน `.local/secrets/gemini_api_key.txt` เท่านั้น
อย่าใส่ key ใน `.env`, frontend, shell history หรือคำสั่งที่พิมพ์ลง log
Compose ส่งไฟล์นี้เป็น secret ให้ `worker` service เท่านั้น; API ตรวจ config แต่ไม่มีไฟล์ key
จากนั้นรัน `docker compose up -d --build` และเปิด [http://127.0.0.1:3000/runs](http://127.0.0.1:3000/runs)
analysis ใน UI ระบุ `mode=real`; mock ยังคงอยู่เมื่อใช้ `.env` ค่าเริ่มต้น

ถ้า project/key/model ใช้ไม่ได้ ระบบแสดง analysis failed/invalid-output ตามสถานะจริง
ไม่มี fallback ไป model ที่เสียเงิน. Rate card/global cost cap, 429 backoff และ production secret store
ยังรอ; ห้ามใช้จริงใน production. หากเปลี่ยนกลับ mock ให้ตั้ง `SOC_AI_PROVIDER=mock` ก่อนเริ่ม run ใหม่

## Provisioning / seed

ตัวอย่าง quota=0 สำหรับบัญชีเตรียมไว้เท่านั้น ไม่ใช่ default policy ของผลิตภัณฑ์
operator ต้องระบุ limits ชัดเจน ไม่มีการย้ายบัญชีจาก prototype

```powershell
docker compose --profile tools run --rm provision user --email instructor@example.test --display-name Instructor --role instructor --daily-runs 0 --daily-ai-requests 0
```

CLI ถาม password และยืนยันด้วย hidden prompt (12–128 chars ไม่ trim), เก็บ Argon2id เท่านั้น
hash parameters ต้องวัดบน hosting ก่อน public ตาม architecture
รันซ้ำด้วยข้อมูล/รหัสเดิมคืน UUID เดิม ไม่เพิ่ม quota/audit ซ้ำ
ถ้า role/name/quota/status/password ต่าง จะปฏิเสธ ไม่ reset หรือยกระดับสิทธิ์เงียบ ๆ
สร้าง Analyst ด้วย `--role analyst` แล้วใช้ UUID ที่ได้:

```powershell
docker compose --profile tools run --rm provision assign --instructor <instructor-uuid> --analyst <analyst-uuid>
```

ตรวจ active roles และ lock user UUID ตามลำดับ; รันซ้ำไม่สร้าง assignment/audit ซ้ำ
noninteractive native test รองรับ `--password-file <private-file>`; ไม่รับรหัสใน command line
อย่า commit ไฟล์นั้น Compose interactive command ไม่ mount account password โดย default

## ฐานทดสอบแยก

```powershell
docker compose --profile test build test
docker compose --profile test run --rm test
```

test-db เป็นอีก service/database `soc_test_foundation`, ไม่เปิด host port และใช้ tmpfs
tests ไม่ชี้ไป db/volume soc ปกติ ต้องมีชื่อ `soc_test_*` และ SOC_TEST_ALLOW_RESET=yes
ก่อน DROP เฉพาะ app/private/ops ในฐานนั้น ไม่ผ่านเงื่อนไขจะหยุด
ถ้าไม่มี test env จะ skip integration ชัดเจน ห้ามนับว่า integration ผ่าน

สำหรับ PostgreSQL แยกที่ operator เตรียมไว้ (ไม่ใช่ production):

```powershell
cd backend
uv sync --frozen
$env:SOC_TEST_DB_HOST = '127.0.0.1'
$env:SOC_TEST_DB_PORT = '55439'
$env:SOC_TEST_DB_NAME = 'soc_test_step02'
$env:SOC_TEST_SECRETS_DIR = (Resolve-Path ../.local/secrets).Path
$env:SOC_TEST_ALLOW_RESET = 'yes'
uv run --frozen python -m pytest -q
```

ครอบคลุม fresh migration rollback/retry, concurrent/repeat/advisory lock, checksum mismatch,
real-role DDL/private/audit restrictions, provisioning races, FK/unique/check constraints,
session hashes, quota counters และ API/worker readiness
HTTPX test client ยังมี upstream deprecation warning แต่ tests ผ่าน ไม่ suppress warning

## Native local execution

สร้าง database soc ด้วย administrator ใน local cluster ก่อน ตั้ง env เฉพาะ shell/process:

```powershell
cd backend
uv sync --frozen
$env:DB_HOST = '127.0.0.1'
$env:DB_PORT = '55432'
$env:DB_NAME = 'soc'
$env:ROLE_SECRETS_DIR = (Resolve-Path ../.local/secrets).Path
$env:DB_PASSWORD_FILE = (Resolve-Path ../.local/secrets/postgres.txt).Path
uv run --frozen python -m app.db.bootstrap
$env:DB_PASSWORD_FILE = (Resolve-Path ../.local/secrets/migration_owner.txt).Path
uv run --frozen python -m app.db.migrate
$env:DB_PASSWORD_FILE = (Resolve-Path ../.local/secrets/api_runtime.txt).Path
uv run --frozen python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

worker ใช้อีก shell กับ env ชุดเดียวกัน แต่ DB_PASSWORD_FILE ชี้ worker_runtime.txt
แล้ว `uv run --frozen python -m app.worker` หรือ `--check` สำหรับ one-shot check.
Evaluator ใช้ process แยก: DB_PASSWORD_FILE ชี้ evaluator_runtime.txt แล้วรัน
`uv run --frozen python -m app.evaluation`; `--check` ตรวจ credentials/migration โดยไม่ claim jobs.
Evaluator role อ่าน private ground truth และเขียน evaluation snapshots ได้; API/browser ไม่มีสิทธิ์อ่านตารางเฉลยโดยตรง.
Ctrl+C เพื่อหยุด ส่วน frontend ใช้ npm run dev/build/start ตามคู่มือเดิม
เมื่อตั้ง DB แล้วให้ตั้ง `SOC_EXPECT_READY_STATUS=200` ก่อน npm test ใน frontend;
กรณีไม่ตั้ง DB ใช้ค่าเริ่มต้น 503 การ smoke ต้องตรงสภาพระบบจริง

## Pins และ recovery

Compose pin PostgreSQL 17.11-bookworm และ digest; Python/Node images ตาม runtime pins เดิม
digests ตรวจจาก official Docker Registry วันที่ 13 ต.ค. 2026 และ pull/build/run บน Linux engine ผ่านแล้ว
เลือก major 17 สำหรับ local; hosting/pgvector/production compatibility ยังรอยืนยัน
อ้างอิง [official PostgreSQL image](https://hub.docker.com/_/postgres),
[Windows binaries](https://www.postgresql.org/download/windows/) และ
[Alembic asyncio](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic)

wrapper ใช้ async SQLAlchemy connection.run_sync + transaction advisory lock และ ledger
SHA-256 source ที่ normalize newline; DDL/Alembic revision/ledger commit พร้อมกัน
checksum/head ผิดให้หยุดตรวจ source/version ไม่แก้ ledger เพื่อหลบ error
transaction fail จะ rollback แล้วค่อยแก้สาเหตุ/รัน wrapper ซ้ำ ไม่มี destructive downgrade
ดู [migration guide](../backend/migrations/README.md); nontransactional migration ต้องออกแบบเพิ่ม
