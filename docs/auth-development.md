# ข้อ 04 — Authentication และ Guest demo

ทำบน `codex/step-04-auth` จาก main `56b49a9` โดยไม่แก้ prototype
ผลตรวจและขอบเขตอยู่ใน [รายงานข้อ 04](step-04-verification.md)

Preview ที่เปิดในงานนี้แยกจาก soc-local: [http://127.0.0.1:13004](http://127.0.0.1:13004)
project soc-auth04 ใช้ API 18004 และ DB 55434 ถ้าต้องเปิดซ้ำ:

```powershell
$env:SOC_WEB_PORT='13004'
$env:SOC_API_PORT='18004'
$env:SOC_DB_PORT='55434'
docker compose -p soc-auth04 up --build -d --wait
# หยุดโดยคงข้อมูล: docker compose -p soc-auth04 down
```

## เปิดทดสอบ

จาก repository root มี Docker Linux engine และ Python ตาม pin:

```powershell
python scripts/init-local.py
docker compose up --build -d --wait
```

เปิด [สมัครสมาชิก](http://127.0.0.1:3000/register), [เข้าสู่ระบบ](http://127.0.0.1:3000/login),
[บัญชี](http://127.0.0.1:3000/account) และ [Guest demo](http://127.0.0.1:3000/demo)
ใช้บัญชีที่สมัครเอง ไม่มี default password; Instructor ยังสร้างด้วย provisioning ตาม [คู่มือ DB](local-development.md)
ผู้ใช้ยืนยัน 22 ต.ค. 2026: บัญชี Analyst ที่สมัครใหม่ใช้รหัสผ่าน 6–12 ตัวอักษร; login และการยืนยันเพื่อเชื่อม Google เดิมยังรับรหัส 5–128 ตัวอักษรเพื่อรักษาบัญชีเก่า ส่วน Instructor ที่ provision ผ่าน operator ยังคง 12–128 ตัวอักษร ไม่แก้ password hashes เก่าและไม่เติมอักขระเพื่อหลบข้อจำกัด provider

Supabase stack ใหม่ใช้ PostgreSQL + server-only Supabase Auth bridge แล้ว ส่วน compose local เดิมยังคง auth local
ดู [คู่มือ Supabase](supabase-migration.md) และ [ผลตรวจ](supabase-verification.md) สำหรับ environment จริง
email confirmation/Google provider settings และการย้ายบัญชีเก่าเป็นคนละเรื่องกับการมี SDK/helper
bootstrap/migrate exit 0 เป็นปกติ; migration 0002 เพิ่ม auth_rate_limits และเก็บข้อมูลจาก 0001 ไว้

Native API ต้องตั้ง DB env ตามคู่มือ DB รวม `AUTH_ORIGINS=http://127.0.0.1:3000,http://localhost:3000`
และ `AUTH_COOKIE_SECURE=false` เฉพาะ loopback HTTP development
HTTPS ใช้ Secure=true (ค่าเริ่มต้น) และระบุ origin ที่ไว้ใจอย่างเจาะจง ไม่ใช้ wildcard
Compose จัด origin ให้ตรง SOC_WEB_PORT จึงทดสอบผ่าน Next.js proxy ได้
ถ้าเปิด Next.js dev server แยกอีกพอร์ต เช่น `127.0.0.1:4175` ให้ตั้ง
`SOC_AUTH_ORIGINS=http://127.0.0.1:3000,http://localhost:3000,http://127.0.0.1:4175`
ก่อนสร้าง API container ใหม่ (เปลี่ยน `3000` ให้ตรง `SOC_WEB_PORT` ที่ใช้อยู่)
แล้วรัน `docker compose up -d --no-deps --force-recreate api`.
ต้องระบุ origin เต็มและเจาะจง; อย่าใช้ wildcard หรือปิด Origin/CSRF validation.

## Contract ที่เปิดจริง

| Endpoints | พฤติกรรม |
|---|---|
| GET /auth/csrf | csrf_token ผูก cookie; pre-auth challenge อายุ 15 นาที |
| POST /auth/register | Analyst เท่านั้น, quota 10/20, 201 user; account/quota/session commit พร้อมกัน, consume challenge และออก session cookie ใหม่ |
| POST /auth/login | generic failure, Argon2id verify; revoke cookie session เดิม, session/CSRF ใหม่; 200 user/expires_at/csrf_token |
| GET /auth/session | active session/user เท่านั้น; 401 ถ้า expired/revoked/disabled |
| POST /auth/logout | active session ต้อง CSRF; revoke atomic/audit; 204 ล้าง cookies; expired/absent logout ซ้ำได้แต่ต้อง Origin |
| GET /me, /me/quota | เลือกผู้ใช้จาก cookie เท่านั้น; ไม่ใช้ client user_id; usage จาก UTC ledger |
| GET /demo/overview, /demo/events, /demo/events/{event_id} | snapshot สาธารณะ 2 events benign แยกจากผู้ใช้/exam; ไม่มี mutation/AI/คะแนน |

ทุก path ในตารางมี prefix /api/v1; unknown body fields ถูกปฏิเสธ
response models ปิด extra fields ไม่ส่ง password/token hashes; errors ไม่สะท้อน input
mutation ต้อง application/json + Origin + X-CSRF-Token (ยกเว้น expired logout ไม่บังคับ token)
register duplicate ตอบ generic REGISTRATION_FAILED ไม่บอก field/account details;
success 201 ตาม contract ยังทำให้ผู้เรียกแยก success/failure ได้ ไม่อ้างว่าปกปิดการมีบัญชีแบบสมบูรณ์

ข้อสรุปผู้ใช้ 21 ต.ค. 2026: สมัครด้วย password สำเร็จแล้วเข้าสู่ระบบทันที หน้าเว็บ refresh session/CSRF แล้วพาไป `/account` เพื่อเริ่มบทเรียน ไม่เรียก login ซ้ำด้วยรหัสผ่านใน frontend; session เดิมใน browser ถูก revoke และ cookie ใหม่เผยแพร่หลัง transaction commit เท่านั้น ข้อนี้แทน policy ไม่ auto-login ในรายงานเก่า

cookie `soc_session`/`soc_challenge`: HttpOnly, SameSite=Lax, Path=/, Secure โดย default
opaque token สุ่ม 32 bytes; DB เก็บ SHA-256 เท่านั้น; CSRF derive แบบ domain-separated HMAC จาก opaque token
session absolute expiry 24 ชั่วโมง; UI ตรวจใหม่เมื่อ refresh/focus และทุก 60 วินาที แต่ API ตรวจทุก request
ไม่มี token ใน localStorage และไม่มี shared caching สำหรับข้อมูลสมาชิก
rate limits เก็บ DB แยก transaction เพื่อให้นับ failed login: login/register 10 requests/minute ต่อ IP และ email,
CSRF bootstrap 30/minute ต่อ IP; 429 พร้อม Retry-After 60; hash keys ไม่เก็บ email/IP ดิบ
บันทึกขั้นเรียนแยกเป็น 60/minute ต่อ IP เพื่อรองรับ 18 saves ต่อระดับ
ยังตรวจ step order, owner, level gate และ expected_version ฝั่ง server ทุกครั้ง
ยังไม่เชื่อ X-Forwarded-For: หลัง proxy ผู้ใช้แชร์ IP bucket ได้ ต้องตั้ง trusted proxy policy ก่อน public hosting
expired counters ลบได้ด้วย retention_runtime; retention scheduler ยังเป็นงานภายหลัง

## สิทธิ์และขอบเขต

ผู้ใช้ยืนยันวันที่ 14 ต.ค. 2026: ผู้สมัครใหม่ได้ 10 รอบฝึก/20 AI requests ต่อวัน UTC
โควตาถูกบังคับใน DB; ปัจจุบันมี runner และระบบข้อสอบเพิ่มเติมแล้ว ดู checklist สำหรับสถานะปัจจุบัน. ส่วนนี้เป็นคู่มือ auth ไม่ใช่รายการ feature ทั้งระบบ
Instructor role ไม่ทำให้ใช้ owner policy อ่านข้อมูลคนอื่นได้; assignment policy ต้อง role Instructor และแถว assignment จริง
ทดสอบ policy ผ่าน api_runtime แล้ว; รายการ admin/run routes ในเอกสารเดิมเป็นสถานะ ณ ตอนเขียน ให้ดู checklist และรายงานตาม commit ก่อนสรุปสถานะปัจจุบัน
Guest demo ข้อนี้เน้นอ่าน HTTP events; catalog เพิ่มแล้วใน [ข้อ 05](scenario-development.md)
ticket/alert/evaluation demo ยัง draft และไม่เอาข้อสอบมาใช้เป็นตัวอย่าง

## Tests และ contract drift

```powershell
cd backend
uv sync --frozen
uv run --frozen pytest -m 'not integration'
uv run --frozen python ../scripts/generate-client-types.py --check
cd ../frontend
npm ci
npx playwright install chromium
npm run lint
npm run typecheck
cd ..
```

เปิด Docker แล้วใช้ Bash/Git Bash เพื่อรัน CI ทั้งชุดใน project ทิ้งได้:

```bash
COMPOSE_PROJECT_NAME=soc-ci-auth04 bash scripts/ci-compose.sh
```

สคริปต์จะ build/migrate/test PostgreSQL, HTTP smoke และ Chromium E2E แล้วลบเฉพาะ CI project/volume
ถ้าทดสอบ UI ที่เปิดไว้เอง ใช้ `SOC_SMOKE_ORIGIN=http://127.0.0.1:3000 npm --prefix frontend run test:e2e`
Browser tests สมัครบัญชี synthetic จริง จึงให้ชี้ฐาน local/test เท่านั้น ไม่ใช้ production
CI ติดตั้ง Chromium dependencies บน Ubuntu; lockfile pin @playwright/test 1.64.0
OpenAPI approved เฉพาะ health และ routes ในตาราง; endpoint อื่นยัง draft
`scripts/generate-client-types.py` สร้าง TypeScript DTOs จาก approved schema; --check และ FastAPI contract tests กัน drift


Google login เป็น optional runtime feature ตามนโยบายที่ผู้ใช้ยืนยัน 16 ต.ค. 2026 ดู [คู่มือ Google OAuth และผลตรวจ](google-login-setup.md). Password registration/login เดิมยังทำงานตามเดิม; new Google registration เข้าใช้ทันทีและ existing-email ต้อง explicit password reauthenticated linking
