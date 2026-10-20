# เริ่มพัฒนาและทดสอบระบบในเครื่อง

> **หมายเหตุสถานะปัจจุบัน:** การกล่าวถึง Gemini ในเอกสารนี้เป็นข้อมูลย้อนหลัง/หลักฐานของ implementation ก่อนเลือก Dify ไม่ใช่คำสั่งให้เปิดใช้หรือสถานะ provider ปัจจุบัน; repository ต้องใช้ Dify API เท่านั้น และ runtime ยังปิดจน integration ผ่านการตรวจรับ

คู่มือนี้รวมเวอร์ชันเครื่องมือ วิธีเปิดหน้าเว็บ/API และคำสั่งตรวจโค้ด เว็บแอปปัจจุบันมีระบบบัญชี การฝึกสืบสวน บทเรียน ข้อสอบ และ RAG แล้ว แต่การเปิดในเครื่องไม่ได้แปลว่า staging หรือ production พร้อม

ถ้าต้องการเปิดชุดระบบที่มี PostgreSQL ให้เริ่มจาก [local development](local-development.md) ถ้าต้องการดูต้นแบบที่ไม่ใช้ฐานข้อมูล ให้ใช้ [คู่มือ prototype](../prototype/README.md)

## Runtime และ dependencies ที่ตรวจแล้ว

| เครื่องมือ | Pin | หลักฐาน |
|---|---|---|
| Node.js / npm | 24.20.0 / 11.19.0 | runtime ที่รัน build/smoke จริง; `.node-version`, package engines และ packageManager |
| Next.js / React / React DOM | 16.4.0 / 19.3.0 / 19.3.0 | npm registry metadata, peer constraints, build จริง |
| TypeScript | 5.9.3 | compiler + typescript-eslint peer range + typecheck จริง |
| ESLint / typescript-eslint / React Hooks | 10.12.0 / 8.71.2 / 7.1.1 | compatible peer constraints + lint จริง |
| Python / uv | 3.12.14 / 0.9.5 | runtime จริง; `.python-version`, exact requires-python, uv required-version |
| FastAPI / Pydantic / Uvicorn | 0.143.0 / 2.14.1 / 0.54.0 | PyPI metadata, uv resolver, API startup/tests |
| SQLAlchemy async / asyncpg / Alembic | 2.1.4 / 0.32.0 / 1.20.0 | native PostgreSQL integration/migration ผ่านในข้อ 02 |
| Argon2-cffi | 25.1.0 | provisioning hash/verify tests ผ่าน |

Direct dependencies pin exact ใน `frontend/package.json` และ `backend/pyproject.toml`;
transitive versions/integrity hashes อยู่ใน `package-lock.json` และ `uv.lock` ใช้ npm/uv ตาม pin
ไม่แก้ lock ด้วยมือ ไม่อัปเกรด runtime โดยไม่ re-resolve และตรวจซ้ำ
PostgreSQL local pin 17.11 พร้อม image digest ใน Compose; Docker build/up/integration ผ่านแล้ว
Source ปัจจุบันมี RAG pipeline ภายในที่ใช้ pgvector/LangChain Core และ Gemini สำหรับ model calls. ทิศทางที่ผู้ใช้ยืนยันคือใช้บริการ RAG ภายนอก (Dify) ผ่าน API เท่านั้น; การเชื่อมต่อดังกล่าวยังไม่ยืนยันใน source. CI ปกติใช้ mock.

ตรวจจาก [Next.js installation](https://nextjs.org/docs/app/getting-started/installation),
[npm Next.js metadata](https://registry.npmjs.org/next/16.4.0),
[npm TypeScript metadata](https://registry.npmjs.org/typescript/5.9.3),
[PyPI FastAPI metadata](https://pypi.org/pypi/fastapi/0.143.0/json)
และ registry ของ dependencies ใน lockfiles เมื่อ 13 ต.ค. 2026 ไม่อ้างว่า pin จะเป็นรุ่นล่าสุดตลอดไป

เลือก ESLint + TypeScript/React Hooks configs โดยตรง เพราะ eslint-config-next ที่ตรวจในวันทำงาน
ดึง braces <=3.0.3 ซึ่ง audit แจ้ง GHSA-vfj7-8cjw-p6xm และไม่มี patch ใน registry
ไม่มีการลด Next.js รุ่นหรือปิด audit เพื่อให้ผ่าน ชุดสุดท้าย npm audit ไม่พบรายการ
Next-specific lint rules ยังไม่ได้รวม; เพิ่มเมื่อ dependency รองรับโดยปลอดช่องโหว่ที่พบ

## ติดตั้ง

ติดตั้ง Node/npm และ Python/uv ตาม pin ก่อน คำสั่งด้านล่างเริ่มจาก root repository
ตัวอย่างใช้ PowerShell; shell อื่นใช้คำสั่ง npm/uv เดียวกันและเปลี่ยน copy syntax

```powershell
node --version
npm --version
python --version
python -m pip install uv==0.9.5
uv --version
cd frontend
npm ci
Copy-Item .env.example .env.local
cd ../backend
uv sync --frozen
```

Python launcher ใน Windows ที่ชี้ WindowsApps อาจเป็น alias ที่ไม่มี interpreter
ให้ติดตั้ง/เลือก Python 3.12.14 จริง และใช้ `uv sync --frozen --python <path-to-python.exe>`
อย่าใส่ absolute path ของเครื่องผู้พัฒนาคนอื่นลง repository
backend `.env.example` ระบุ DB_HOST/PORT/NAME และ DB_PASSWORD_FILE สำหรับ shell configuration
ไม่ได้ auto-load .env; Compose ส่ง environment/secrets ให้โดยตรง ไม่มี default password/provider key

## เปิด API และ UI

Terminal 1 จาก `backend/`:

```powershell
uv run --frozen python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2 จาก `frontend/`:

```powershell
npm run dev
```

เปิด [หน้าเริ่มต้น](http://127.0.0.1:3000), [API docs ของ routes ที่ implement แล้ว](http://127.0.0.1:8000/docs)
และ [health ผ่าน same-origin proxy](http://127.0.0.1:3000/health/live)
`/health/live` ตอบ 200 พร้อม envelope/request ID;
`/health/ready` ตอบ 503 เมื่อไม่มี DB config หรือ schema ยังไม่พร้อม เมื่อตั้ง DB แล้วจะตรวจ runtime role, Alembic head และ checksum ก่อนตอบ 200
Swagger แสดงเฉพาะ API contract ที่อนุมัติแล้ว บาง endpoint ที่ implement ไว้ เช่น exam ยังอยู่ใน OpenAPI draft จึงไม่แสดงเป็น contract ที่อนุมัติ ดู [API contract](api.md) และ [OpenAPI](openapi.yaml) ควบคู่กัน

Frontend ใช้ rewrite `/api/v1/*` และ `/health/*` ไป FastAPI; BACKEND_ORIGIN เป็น server-only
localhost URL ไม่มี credential ไม่ใช้ NEXT_PUBLIC สำหรับ secrets
rewrite destination อ่านตอน build; เปลี่ยน origin ของ standalone ต้อง build ใหม่ใน local
production จะใช้ ingress same-origin ตาม architecture เมื่อทำข้อ 18

ทดสอบ production-style local server จาก `frontend/` (หยุด dev server ก่อน):

```powershell
npm run build
npm run start
```

postbuild คัดลอก `.next/static` และ `public` ถ้ามีเข้า standalone; start ใช้
`.next/standalone/server.js` โดย bind 127.0.0.1 ค่าเริ่มต้น
`PORT` เปลี่ยนพอร์ตได้; `SOC_BIND_HOST` ใช้กำหนด interface เมื่อ environment พร้อม
คำสั่งนี้ไม่ publish/deploy; Ctrl+C เพื่อหยุดแต่ละ process

## Worker

จาก `backend/`:

```powershell
uv run --frozen python -m app.worker --check
```

ต้องตั้ง DB env และ secret ของ worker_runtime ตาม local database guide
`--check` คืน exit 0 เมื่อ database_ready=true, exit 2 ถ้าไม่พร้อม; queue_ready=false เสมอในข้อ 02
ไม่มี --check จะรายงาน foundation status ทุก 30 วินาทีและรอหยุดอย่าง graceful
Worker รับงานจาก PostgreSQL queue และตรวจ lease ก่อนบันทึกผล ใช้ `--check` เพื่อตรวจ readiness โดยไม่เริ่มทำงานค้างใน queue

## คำสั่งตรวจ

จาก `backend/`:

```powershell
uv run --frozen python -m ruff check app tests
uv run --frozen python -m ruff format --check app tests
uv run --frozen python -m mypy app
uv run --frozen python -m openapi_spec_validator ../docs/openapi.yaml
uv run --frozen python -m pytest -q
```

จาก `frontend/`:

```powershell
npm run lint
npm run typecheck
npm run build
npm audit
# เริ่ม API + npm run start ใน terminals แยกก่อน:
npm test
```

`npm test` เป็น smoke ผ่าน HTTP จริง 3 ข้อ ใช้ Node built-in test runner ไม่ใช่ full feature E2E
ตั้ง `SOC_SMOKE_ORIGIN` เมื่อเปลี่ยนพอร์ต ค่าเริ่มต้น http://127.0.0.1:3000
ตั้ง SOC_EXPECT_READY_STATUS=200 เมื่อใช้ DB ที่พร้อม; ค่าเริ่มต้น 503 สำหรับ scaffold ที่ไม่ตั้ง DB
integration tests ต้องใช้ฐานแยกพร้อม opt-in ตาม local database guide มิฉะนั้นจะ skip อย่างชัดเจน
backend tests ตรวจ contract, permissions, database transactions และ flow สำคัญตามชุดที่ระบุ ดูรายงานข้อ 14–19 เพื่อทราบว่าส่วนใดทดสอบแล้วและส่วนใดยังรอรับรอง
Frontend ใช้ Playwright สำหรับ browser regression; ไม่ได้ติดตั้ง Vitest/Testing Library

## เปลี่ยน contract ในขั้นถัดไป

แก้ `docs/openapi.yaml` โดยตรง; domain operations ที่ยังไม่ implement เป็น draft และระบุ schema gaps
responses ที่ไม่มี content schema หมายถึง **ยังไม่อนุมัติ payload** ไม่ใช่ยอมรับ JSON อะไรก็ได้
ก่อนเพิ่ม route ต้องตกลง policy ใน SRS, เติม explicit request/response models และเปลี่ยนเฉพาะ
operation นั้นเป็น approved พร้อม behavior tests. Test จะ fail ถ้า FastAPI เพิ่ม route
ที่ไม่มีใน approved subset หรือ schema ของ implementation drift
ห้าม export OpenAPI จากแอปทับไฟล์ทั้งฉบับจน domain draft inventory หาย

ใช้ `python -m app.db.migrate` ตาม [migration guide](../backend/migrations/README.md)
ไม่เรียก Alembic upgrade โดยตรงเพื่อข้าม advisory lock/checksum ledger
