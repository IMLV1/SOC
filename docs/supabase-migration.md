# ย้าย PostgreSQL และ Auth ไป Supabase

## Implementation ใหม่ — 22 ต.ค. 2026

ส่วนนี้ supersede สถานะ “เตรียม config เท่านั้น” ในบันทึกเดิมด้านล่าง
อ่าน [ผลตรวจล่าสุด](supabase-verification.md) ก่อนสรุปว่า runtime หรือ Google พร้อม

### Auth boundary

- FastAPI ส่ง signup/password/PKCE ไป Supabase Auth REST API ผ่าน HTTPS
  Supabase เป็นเจ้าของ credentials; บัญชีใหม่ใน `app.users` ไม่มี local password hash
- Next.js ยังคงเรียก same-origin `/api/v1`; ไม่ query domain tables ผ่าน public Data API
- จับคู่ Supabase subject UUID กับ SOC user ID; ไม่ email auto-merge
  ไม่ใช้ user metadata กำหนด role/quota/score/unlock; สมัครใหม่ Analyst quota 10/20 เท่านั้น
- Browser ได้ opaque `soc_session` HttpOnly/SameSite=Lax/Secure ตาม environment และ CSRF เดิม
  ไม่มี Supabase access/refresh token ใน JSON หรือ client storage
- Provider tokens เก็บ Fernet-encrypted ฝั่ง server ด้วย key file แยกจาก DB
  ตรวจ Auth `/user` ก่อนเปิด domain transaction และตรวจ owner/assignment/status ตามเดิม
- Operator สร้าง `ops.supabase_session_active(subject,session_id)` แบบ boolean SECURITY DEFINER
  อ่าน existence/expiry ของ `auth.sessions` และ banned/deleted users เท่านั้น
  owner เป็น operator, search_path ตรึง pg_catalog, PUBLIC ไม่มี EXECUTE
  API ได้ EXECUTE เท่านั้น ไม่มี SELECT/UPDATE schema auth; worker/evaluator ไม่ได้สิทธิ์นี้
- Refresh ใช้ lease/version fencing และ network นอก DB transaction
  ถ้าไม่ทราบผล ไม่ dispatch refresh token เดิมซ้ำ; หลัง lease หมดต้อง login ใหม่
  concurrent refresh แสดง 503 AUTH_REFRESH_PENDING ชั่วคราว ไม่สร้าง session ปลอม
- Logout revoke SOC session/ล้าง encrypted tokens ก่อนเรียก Supabase logout
  provider outage ไม่ทำให้ cookie เก่ายังใช้ SOC ได้; absolute session expiry 24 ชั่วโมง

SDK/helpers frontend เดิมยังเป็น preparation/reference ไม่เปิด root Proxy หรือใช้ SDK session
อีกชุดควบคู่กับ FastAPI BFF จึงไม่สร้าง authoritative auth สองแหล่ง

### Cloud database/operator

`app.db.supabase_setup` ใช้กับ fresh managed project โดย opt-in `SOC_SUPABASE_SETUP=yes`
ปฏิเสธ existing SOC roles/schema ไม่ adopt/rotate รหัสเงียบ ๆ
ไม่ใช้ local bootstrap ที่ revoke database/public grants; ไม่เปลี่ยน managed auth schema
ติดตั้ง vector 0.8.2 ที่ migration 0012 เดิมต้องใช้ ไม่เปิด local RAG หรือ Dify
PostgreSQL 17 ให้ creator ADMIN ผ่าน role ใหม่อยู่แล้ว จึงเปิด SET/INHERIT โดยไม่ grant ADMIN ย้อนกลับ

Migration ใหม่ `0021_supabase_auth` เพิ่ม identity mappings, encrypted provider sessions และ PKCE flows
ใช้ migration wrapper/advisory lock/checksum ledger เดิม ไม่แก้ migrations เก่า
runtime ใช้ `api_runtime`, `worker_runtime`, `evaluator_runtime` แยก credentials
operator ใช้ `migration_owner`; ไม่มี runtime รับ postgres password/service_role key

`compose.supabase.yaml` แยกจาก local stack และไม่มี local DB หรือ migration/seed ใน startup
ไฟล์ `.local/supabase/runtime.env` กับ credentials เป็น ignored/private เฉพาะเครื่อง
กำหนด UID/GID, project, session host, CA, exact origins/callback ให้ตรง environment

```bash
docker compose --env-file .local/supabase/runtime.env -f compose.supabase.yaml --profile operator build api worker seed
docker compose --env-file .local/supabase/runtime.env -f compose.supabase.yaml --profile operator run --rm --no-deps migrate
docker compose --env-file .local/supabase/runtime.env -f compose.supabase.yaml --profile operator run --rm --no-deps seed
docker compose --env-file .local/supabase/runtime.env -f compose.supabase.yaml up -d api worker evaluator
```

คำสั่งนี้ใช้หลัง fresh operator bootstrap สำเร็จเท่านั้น ไม่รัน setup ซ้ำบน project ที่มี SOC data
ไม่ใช้ local checksum recovery overlay กับ cloud ใหม่
Frontend ต้องชี้ BACKEND_ORIGIN ไป stack ใหม่; แค่มี public URL/key ไม่ได้สลับ DB
HTTPS ต้องเปิด Secure cookie; false ใช้เฉพาะ local HTTP เท่านั้น

### Signup/Google และข้อมูลเก่า

- สมัคร 6–12 ตัว: ถ้า provider ออก session คืน 201 user + cookie และเข้าสู่ระบบทันที
- ถ้า Supabase บังคับยืนยัน email คืน 202 `email_confirmation_required` ไม่มี SOC account/session ปลอม
  ยืนยันผ่าน email ของ Supabase แล้วกลับมา login ไม่ปิด confirmation ให้เอง
- Google status อ่าน Auth `/settings`; UI ไม่อ้างพร้อมถ้า provider ปิด
- Google PKCE s256 + browser/session binding, flow อายุ 5 นาที consume ก่อน exchange
- ตั้ง Google Client ID/Secret ใน Supabase Dashboard ด้วยมือ ไม่ใส่ secret ใน Git/แชต
  Google authorized callback ใช้ `https://<project>.supabase.co/auth/v1/callback`
  Supabase Redirect URLs ต้องอนุญาต exact SUPABASE_AUTH_CALLBACK_URL ผ่าน origin ของเว็บ
- ไม่มี automatic linking จาก SOC email เดิม; หน้า account แจ้งข้อจำกัด
  ไม่เปิด local-password linking form ใน Supabase mode
- ฐาน local/บัญชี/ประวัติเดิมยังอยู่ ไม่ย้าย Argon2 hash หรือรวม ownership อัตโนมัติ
  เป็น fresh data environment ไม่ใช่การยืนยัน migration บัญชีเก่า

Backup ต้องเก็บ token key อย่างปลอดภัยแยกจาก DB; ก่อน production ต้อง restore drill/revoke restored sessions
Retention ต้องลบ supabase_sessions ก่อน auth_sessions; scheduler/production backup ยังไม่ถือว่าพร้อม
Dify ยังปิด AI mock; การย้าย DB/Auth ไม่ทำให้ AI/exam/learning acceptance ที่ค้างผ่านเอง

อ้างอิง [Auth sessions](https://supabase.com/docs/guides/auth/sessions)
และ [REST contract](https://github.com/supabase/auth/blob/master/openapi.yaml)

---

## บันทึกช่วงเตรียมก่อน implementation (ประวัติ ไม่ใช่สถานะ runtime ล่าสุด)

ข้อตัดสินใจผู้ใช้ 22 ต.ค. 2026:

- Database: Supabase PostgreSQL
- สมัครสมาชิก/login/Google: Supabase Auth
- สมัครใหม่ใช้รหัสผ่าน **6–12 ตัวอักษร** ไม่เติมอักขระในรหัสเพื่อหลบ policy
- Next.js ยังคงเป็น frontend, FastAPI เป็นเจ้าของ domain/permissions, Python worker ยังปล่อย event และทำงาน durable jobs
- Dify เป็น AI/RAG ภายนอก ไม่เปลี่ยนไปใช้บริการ AI ของ Supabase

## สถานะ: เตรียม config/clients เท่านั้น ยังไม่ cut over

มี SDK ที่ปักเวอร์ชันใน frontend และ helpers browser/server/proxy แล้ว แต่ยังไม่มี root `proxy.ts`
หรือการเปลี่ยนหน้า login/register ให้ใช้ Supabase Auth
FastAPI ยังใช้ auth เดิมและยังไม่รับ Supabase token เป็น session
ไม่มี external calls, cloud migrations, seed หรือการแก้ PostgreSQL local ในงานเตรียมนี้
อย่าตั้งค่าแล้วอ้างว่าล็อกอิน Supabase ได้ทั้งระบบ

## Database configuration

ใช้ [backend/.env.supabase.example](../backend/.env.supabase.example) เป็น template ของแต่ละ process
ตัวแปรไม่ได้ถูก load อัตโนมัติ ต้อง inject ผ่าน shell/process manager/hosting ของ environment ที่เลือก
อย่าเปลี่ยน `.env` ของ local stack เดิมเพื่อทดลอง cloud

| ตัวแปร | ความหมาย |
|---|---|
| `DB_PROVIDER=supabase` | เปิดการตรวจ config สำหรับ Supabase; default เดิมยังเป็น `postgres` |
| `DB_PROJECT_REF` | project reference 20 ตัวจาก Dashboard |
| `DB_CONNECTION_MODE` | `direct` หรือ shared pooler แบบ `session` |
| `DB_HOST` | host จากหน้า Connect; direct ต้องตรง `db.<project-ref>.supabase.co` |
| `DB_PORT=5432` | งานนี้ไม่รองรับ transaction mode/6543 |
| `DB_NAME=postgres` | ชื่อฐานของ project; ไม่ใช่ชื่อ schema |
| `DB_PASSWORD_FILE` | ไฟล์รหัสผ่านของ dedicated role สำหรับ process นั้น ไม่ใช่ publishable/service_role API key |
| `DB_SSL_CA_FILE` | optional CA certificate ของ provider แบบ read-only; ยังคงตรวจ hostname/certificate |

Direct ใช้ DB role เดิม เช่น `api_runtime`; shared session pooler ส่ง username
`api_runtime.<project-ref>` แต่ PostgreSQL `current_user` ต้องยังเป็น `api_runtime`
API/worker/evaluator/migration/retention แยกรหัสและ grants กัน ไม่มี `DB_USER` override ให้ API กลายเป็น postgres
ห้ามให้ runtime ใช้ owner/admin หรือ service_role API key
URL สร้างด้วย SQLAlchemy `URL.create` รองรับอักขระพิเศษใน password โดยไม่ประกอบ DSN ด้วย string

Direct เหมาะกับ long-running backend ที่เข้าถึง network ของ project ได้;
session pooler เป็นทางเลือกเมื่อ network ของ hosting ไม่รองรับ direct connection
ตรวจค่าจาก project จริง ไม่เดาว่า host/region/mode ใดใช้ได้
ดู [การเชื่อมต่อทางการ](https://supabase.com/docs/guides/database/connecting-to-postgres)
และ [SQLAlchemy](https://supabase.com/docs/guides/troubleshooting/using-sqlalchemy-with-supabase-FUqebT)

### ก่อนรัน cloud migrations

1. ยืนยัน project/environment และ database version/extension compatibility กับ Alembic graph จริง
2. ทำ backup และเตรียม dedicated roles/schema/grants แบบ operator โดยไม่กระทบ schema ของ Supabase Auth
3. **อย่ารัน local `app.db.bootstrap` กับ project จริงตรง ๆ**: มี REVOKE/role/extension setup สำหรับ local ที่ต้องตรวจผลกระทบก่อน
4. ตรวจ pgvector version/schema ตาม migration ปัจจุบัน แม้ RAG เปลี่ยนไป Dify ก็ยังมี migration เดิมที่ต้องผ่าน
5. ใช้ migration wrapper/checksum ledger เดิมกับ `migration_owner` หลัง preflight ผ่าน ไม่ใช้ dashboard SQL ข้าม ledger
6. แยก seed/provision เป็น one-shot ไม่ทำใน API startup
7. ตรวจ role isolation, private truth, grants, readiness, concurrency, persistence และ restore ก่อนชี้ traffic

ยังไม่มี DB Host/mode, dedicated-role credentials, CA และผลตรวจ project compatibility ที่ยืนยันได้
publishable key ที่ส่งก่อนหน้าไม่ใช่ PostgreSQL password

## Next.js Auth clients ที่เตรียมไว้

กำหนด `NEXT_PUBLIC_SUPABASE_URL` และ `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` ใน ignored `.env.local`
ของ frontend/hosting เมื่อถึงขั้นเปิด integration เท่านั้น ไม่ใส่ server secret/DB password
config helper รับเฉพาะ standard HTTPS project URL และ `sb_publishable_*`, ปฏิเสธ secret key/legacy JWT

- `src/utils/supabase/client.ts`: browser factory ใช้ SSR cookie storage ไม่สร้าง localStorage session เอง
- `src/utils/supabase/server.ts`: factory ต่อ request สำหรับ cookie-writable Route Handler โดยรับ response headers
  เพื่อส่ง no-cache headers ของ SDK; ไม่กลืน cookie write errors ใน read-only Server Component
- `src/utils/supabase/proxy.ts`: เตรียม `updateSession`, เรียก `getClaims` และรักษา refresh cookies/cache headers
  **ยังไม่ได้เรียกจาก root Proxy** จึงไม่เพิ่ม network/session ใหม่ให้เว็บเดิม

Helpers ไม่ query `todos`/domain tables และไม่แทน FastAPI permissions
ต้องตรวจทั้ง token และสิทธิ์ของ SOC ฝั่ง server ก่อนใช้ข้อมูลสมาชิก
ดู [SSR](https://supabase.com/docs/guides/auth/server-side/creating-a-client)
และ [Google login](https://supabase.com/docs/guides/auth/social-login/auth-google)

## งาน Auth ที่ยังต้อง implement/test ก่อนสลับระบบ

- Identity mapping ระหว่าง Supabase user ID กับ SOC user ID เดิม โดยพิสูจน์เจ้าของบัญชี ไม่ merge จาก email เฉย ๆ
- เส้นทาง signup/login/Google callback/refresh/logout และ CSRF/Origin ที่ทำงานร่วมกับ FastAPI ได้จริง
- ตรวจ token issuer/signature/audience/expiry และ revocation ตาม provider พร้อม owner/assignment checks เดิม
- Provision Analyst/quota 10/20 ฝั่ง server เท่านั้น ไม่เชื่อ role/quota/score จาก user metadata
- วางแผนย้ายผู้ใช้รหัส Argon2 เดิม ไม่สมมติว่า hash เดิมย้ายตรงไป Supabase ได้ และไม่แอบเก็บ plaintext
- รักษา email-confirmation policy ของ project: ถ้าต้องยืนยัน email ต้องแสดง pending ไม่สร้าง session ปลอม
- ตั้ง Google Client ID/Secret ใน Supabase Dashboard และ exact callback/site redirect allowlist; ไม่ส่ง secret เข้าแชต/Git
- ย้าย/expire session เดิมอย่างชัดเจน มี rollback และทดสอบ account collision, disabled user, refresh/logout/cross-user refs
- ตรวจ public Data API ไม่เปิด app/private/ops/kb โดยไม่ตั้งใจ ไม่เอา service_role key ไปใช้แทนสิทธิ์ทั้งหมด

ยังไม่ถือว่าเปลี่ยน auth สำเร็จจากการมี SDK/helper หรือการตั้ง public URL/key เพียงอย่างเดียว
Password validation 6–12 ใช้กับ registration ปัจจุบันแล้ว; login เก่ายังรับ 5–128 ชั่วคราวเพื่อไม่ทำลายบัญชีเดิม

## ผลตรวจการเตรียม local — 22 ต.ค. 2026

ฐาน source `a1fc962` และ working tree นี้ ยังไม่ใช่ Supabase deployment หรือ auth cutover

- Backend `ruff check`/`ruff format --check`: ผ่าน; `mypy app`: ผ่าน 88 source files
- `pytest -m 'not integration'`: **131 passed / 84 deselected** ใน container `--network none`
- ชุดเจาะจง Supabase DB config/password/preview: **35 passed** ไม่เปิด DB connection
- OpenAPI validator และ generated client type drift check: ผ่าน
- Frontend `npm run lint`, production `npm run build` รวม TypeScript: ผ่านใน container แยกปิด network
- Public Supabase config tests: **14 passed**; production browser asset leakage guard: **1 passed**
- Browser registration policy: **1 passed** โดย mock ทุก API ตรวจ 6–12 สำหรับสมัครใหม่ และ 5–128 สำหรับ login เดิม
- Guard เดิมที่ห้าม `NEXT_PUBLIC_*` ทั้งหมดถูกแทนด้วย exact allowlist สองชื่อและค่าว่าง
  เพราะผู้ใช้อนุมัติ Supabase Auth แล้ว; ยังคงห้าม browser DB secrets และ private fixtures
- ไม่รัน integration tests/real signup/Google OAuth กับ local หรือ cloud DB ในรอบนี้

เพื่อให้หน้าเว็บ local กับ API ไม่ใช้ validation คนละรุ่น ตรวจ hash ของ `app/auth/models.py`
ใน API container ว่าตรงกับฐาน source ก่อนอัปเดตไฟล์นั้นและ restart **เฉพาะ API**
ตรวจ schema จาก runtime ได้ registration 6–12, login 5–128 โดยไม่สร้างบัญชีหรือแก้ข้อมูล
ไม่เปลี่ยน env/mount ของ API และไม่รัน migration/seed
นี่เป็น hot update ของ local container เท่านั้น เมื่อ recreate ต้อง build image จาก source ใหม่
ไม่ใช้วิธีนี้แทน immutable release/deployment บน hosting

GitHub CI, Supabase project connection/roles/extensions, identity migration, Google login จริง
และ staging/production acceptance ยังรอยืนยัน ไม่อ้างว่าระบบย้ายไป Supabase แล้ว
