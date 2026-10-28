# Supabase integration verification — 22 ต.ค. 2026

## Follow-up: สถานะบัญชี Google

ผู้ใช้เปิด Google provider ภายหลัง initial verification ด้านล่าง; ตรวจ public status ได้ available=true
แก้ linked=false ตายตัวใน Supabase mode เป็นสถานะจาก identities ใน Auth `/user` ที่ server ตรวจแล้ว
และต้องมี active SOC session ไม่ใช้ user_metadata หรือ query parameter เป็นข้อยืนยัน
หน้า account เอาข้อความย้ายระบบออก แสดง linked/unlinked ตาม API และไม่แสดง success จาก URL อย่างเดียว
ใช้ skill bug-fix ไล่ถึง API/identity boundary ไม่เพียงซ่อนข้อความ
ผลตรวจรอบนี้: backend offline 149 passed, lint/mypy ผ่าน; frontend production build/asset guard ผ่าน
browser Google/Supabase regression 8 passed (API mocks) รวม linked/unlinked, refresh และ forged success URL
ไม่รัน DB integration ใหม่ในรอบแก้ข้อความ/identity projection นี้ ไม่อ้างว่าเป็น real OAuth acceptance
อัปเดต API image ของ local Supabase stack เท่านั้น ไม่ migrate/seed/commit/push/deploy ภายนอก

## Initial Supabase cutover snapshot

ฐาน source `a1fc962`, branch main ahead origin/main 1 commit และ working tree ที่ยังไม่ commit
รายงานนี้ไม่ใช่ CI ของ GitHub หรือ production deployment

## สิ่งที่เปิดจริงในเครื่อง

- เว็บ `http://127.0.0.1:4175` proxy ไป API stack ใหม่ `http://127.0.0.1:8440`
- `soc-supabase` แยก API/worker/evaluator ใช้ Supabase session pooler port 5432
  TLS ตรวจ CA และ hostname; ไม่มี postgres/admin password ใน runtime
- PostgreSQL 17.11; migrations 0001–0021 ผ่าน wrapper/checksum ledger
  head `0021_supabase_auth`; ไม่แก้ revisions เก่าหรือ ledger checksum
- Fresh SOC schemas/roles สร้างใน transaction; ไม่ revoke database/public grants ของ Supabase
  ไม่แก้ managed auth schema; boolean session predicate อ่านอย่างเดียว
- Seed สำเร็จ: training scenarios 5, lesson ที่รองรับ backend จริง 1 และ exam seed เดิม
  JSON preview 3 ระดับยังเป็น preview ไม่อ้างว่ามี server-side progression ใหม่ครบ 3 ระดับ
- API `/health/ready` 200; runner/evaluator readiness true; catalog 200
- `current_user=api_runtime`, database=postgres; ไม่มี anon/authenticated/service_role USAGE บน app
  API มี USAGE private ตาม migration เดิมสำหรับ scoped functions ไม่เท่ากับ SELECT private tables
- ตรวจ runtime จริง: SELECT private.ground_truth=false, USAGE auth=false,
  CREATE public/app=false; scoped session predicate เรียกได้แต่ session ที่ไม่มีจริงคืน false
- Supabase Auth settings ติดต่อได้: email enabled, signup allowed, email autoconfirm=false
  **Google provider ยังปิด**; UI แจ้ง unavailable ตามจริง ไม่อ้าง Google OAuth ผ่าน
- Same-origin CSRF → invalid login ทดสอบผ่าน proxy ได้ 401 AUTH_PROVIDER_REJECTED
  ไม่สมัครบัญชีทดสอบบน managed Auth หรือส่งอีเมลแทนผู้ใช้

ฐาน local/ผู้ใช้/ประวัติเก่าไม่ได้ลบหรือแก้ schema; frontend container เก่าเก็บแบบหยุดไว้
ชื่อ `soc-ui-demo-local-db-backup-20261022` เพื่อ rollback proxy ถ้าจำเป็น
การสลับ DB ทำให้ cookie local เดิมใช้กับ Supabase ไม่ได้ ต้องสมัคร/เข้าสู่ระบบใหม่
ไม่มีการ auto-merge email หรือย้าย Argon2 hash จาก local Auth ไป Supabase

## ผลตรวจที่รันแล้ว

- Backend Ruff lint ผ่าน; mypy ผ่าน 91 source files
- Non-integration tests: **143 passed** ใช้ container --network none
- Integration ทั้งชุดบน PostgreSQL ทิ้งได้: **92 passed** รวม refresh/logout race และ PKCE replay
  รวม migrations, roles, CSRF, quota, auth, runner, tickets, exam และ evaluation เดิม
- Supabase integration ใช้ provider fake แต่ PostgreSQL จริง ไม่ใช่ cloud authentication benchmark
  ตรวจ subject mapping, Analyst/quota server-side, encrypted tokens, confirmation pending,
  provider session revocation predicate, refresh และ logout แม้ provider outage, email collision
  refresh พร้อมกันไม่ dispatch token ซ้ำ และ logout fencing กัน response ที่กลับมาช้า
- Frontend lint/production build รวม TypeScript ผ่าน; public config tests 14 และ asset leakage guard 1 ผ่าน
- Browser Supabase tests **2 passed**: pending confirmation ไม่แสดง login ปลอม,
  Google navigation เฉพาะ fixed Supabase authorization origin; mock API ทั้งหมด
  รอบแรก Chrome ถูก sandbox ปิดก่อนเริ่ม; รันใหม่ด้วยสิทธิ์เปิด Chrome แล้วผ่าน
  pending test พบ dev bundle เก่าใน bind mount; restart frontend แล้ว assertion เดิมผ่าน ไม่ลด timeout
- Browser regression รวม preview/run feedback/Google/Supabase: **16 passed** หลังสลับ proxy
  API ทั้งหมดในชุดนี้เป็น mocks; responsive preview/Google ตรวจ 375/768/1440px

คำสั่งหลัก:

```bash
# ใน backend test runtime ตาม pin
ruff check app tests migrations ../scripts
mypy app
python -m pytest -m 'not integration' -q -p no:cacheprovider
# Integration ต้อง SOC_TEST_DB_NAME=soc_test_* และ SOC_TEST_ALLOW_RESET=yes บนฐานทิ้งได้เท่านั้น
python -m pytest -m integration -q -p no:cacheprovider
# จาก frontend
npm run lint
npm run build
node --test tests/assets.test.mjs tests/supabase-config.test.mjs
```

## สิ่งที่ยังต้องทำกับ project จริง

1. ผู้ใช้สมัครด้วยอีเมลจริงและยืนยันอีเมล จากนั้น login → training → events → pause/resume → logout/relogin
   ยังไม่อ้างว่า successful cloud signup/Google/live learner run ผ่านจาก provider fake
2. ตั้ง Supabase Site URL/Redirect URLs ให้ตรงเว็บ โดยเฉพาะ callback
   `http://127.0.0.1:4175/api/v1/auth/google/callback` ของ local นี้
   Google Console callback ต้องเป็น `https://<project>.supabase.co/auth/v1/callback`
3. เปิด Google provider พร้อม Client ID/Secret ใน Supabase Dashboard แล้วทดสอบ consent/callback จริง
   ไม่ส่ง secret ในแชต/Git; ยังไม่มีข้อมูล Google credentials ที่ใช้ตั้งให้ครบ
4. แผนย้าย existing accounts/ประวัติและ Instructor provisioning ต้องยืนยัน identity แยก
   ห้ามใช้ local-password provisioning สร้างบัญชีที่เข้า Supabase Auth ไม่ได้แล้วอ้างว่าพร้อม
5. Staging/HTTPS, restore drill, backup, retention, load acceptance, CI SHA ล่าสุดยังรอยืนยัน
   Dify ยังปิด/AI mock; ไม่ถือว่าการย้าย Supabase ทำให้ AI/RAG หรือ curriculum ครบเอง

## ไฟล์หลัก

- `backend/app/auth/supabase_provider.py`, `supabase_service.py`: Auth transport, identity/refresh/PKCE bridge
- `backend/app/auth/{routes,service,google_routes}.py`, `app/main.py`: คง cookie/CSRF/domain checks เดิม
- `backend/app/db/supabase_setup.py`, config และ migration 0021: roles/TLS/schema/session storage
- `compose.supabase.yaml`: runtime แยกจาก local DB; migration/seed เฉพาะ operator profile
- `frontend/src/app/auth-form.tsx`, `src/features/google-login.tsx`: pending/errors/fixed provider origin
- OpenAPI/generated DTO/tests: contract และ behavior regressions ไม่เปิด exam/provider scope เพิ่ม

ใช้ skill write-clean-code เพื่อคง transport/session/domain boundary แยกชัดเจน
ไม่ย้าย domain API ไป Next.js และไม่เปิด SDK session อีกชุดขนานกับ opaque SOC session
เก็บกวาดเฉพาะ PostgreSQL tmpfs/network ทดสอบที่สร้างในงานนี้แล้ว ไม่แตะ volumes/ฐานผู้ใช้

## Follow-up: session guard หน้า Login/Register (2026-10-22)

- `AuthForm` ใช้ผล `/api/v1/auth/session` จาก `SessionProvider` ชุดเดียวกับ navbar:
  session ที่ยืนยันแล้ว redirect ด้วย `replace` ไป `/account`; ระหว่างรอไม่แสดงฟอร์ม
- 401 แสดงฟอร์มสำหรับ guest; API outage ไม่ถือว่า logout และมีปุ่มตรวจสอบอีกครั้ง
- ใช้ skill `bug-fix` แก้ต้นเหตุที่ฟอร์มไม่ได้อ่าน session เดิม ไม่เพิ่มระบบ auth อีกชุด
- Browser regression `auth-navigation.spec.ts google-login.spec.ts supabase-auth.spec.ts`:
  **16 passed** บน local `http://127.0.0.1:4175` โดย mock API รวม delayed session,
  refresh, logout และ retry หลัง 503; ไม่ใช่ผลยืนยัน session ของบัญชีจริง
- Frontend lint, production build/TypeScript และ asset leakage guard **1 passed**
  ใน container แยก; ไม่เปลี่ยน backend, migrations หรือข้อมูล Supabase ใน follow-up นี้
- ผลนี้เป็น local working tree บน `main` หลัง `a1fc962` ไม่ใช่ GitHub CI หรือ deployed acceptance
