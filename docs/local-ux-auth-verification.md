# Local learner flow และ password policy — 21 ต.ค. 2026

ตรวจจาก working tree บน `main` ที่มี base commit `e7696f4`; ผลนี้ยืนยันเฉพาะ environment local ไม่ใช่ GitHub CI หรือ deployment สาธารณะ

## พฤติกรรม

- หน้าแรกพา Guest ไป `/demo` เพื่อกดอ่าน Method → Path → Response status → Time โดยไม่บันทึก progress/คะแนน; ใช้ public benign snapshot เดิม ไม่ใช้ exam fixtures
- หน้าบัญชีพาไปบทเรียนก่อนข้อสอบ และแยกทางไปรอบฝึก; บทเรียนเปิดคำอธิบายหลังเลือกข้อมูลตัวอย่าง การเลือกเป็นการนำทางใน UI ไม่ใช่หลักฐานสอบผ่าน
- ฟอนต์ที่ให้บริการจาก frontend คือ JetBrains Mono สำหรับ Latin และ Anakotmai สำหรับภาษาไทย พร้อมแหล่งที่มาใน `frontend/public/fonts/README.md`
- ตามคำขอผู้ใช้ สมัคร Analyst ใหม่รับ password 5–10 ตัวอักษร; login/Google linking รับ 5–128 เพื่อรักษาบัญชีเดิม ส่วน operator provisioning ยังคง 12–128 ไม่มีการเปลี่ยน password hashes หรือ migration
- Origin allowlist ตั้งผ่าน `SOC_AUTH_ORIGINS` ได้เมื่อใช้ dev server คนละพอร์ต; CSRF/Origin checks ยังคงบังคับ

## Environment และหลักฐาน

Next.js dev ที่ `127.0.0.1:4175` proxy ไป API `127.0.0.1:8400` ของ Compose project `soc-verify-steps` ใช้บัญชี synthetic ในการทดสอบ ไม่มีการเรียก AI provider จริง

- Python 3.12.14 test image: `ruff check app tests`, `ruff format --check app tests`, `mypy app` ผ่าน
- `pytest -q -m 'not integration' -p no:cacheprovider`: **103 passed, 82 deselected** รวม password boundaries และการยอมรับรหัสเดิมยาว 128 ตัวอักษร
- `python -m openapi_spec_validator /docs/openapi.yaml` และ `generate-client-types.py --check`: ผ่าน; approved schema drift tests อยู่ใน non-integration suite
- Frontend `npm run lint`, `npm run build` (รวม TypeScript check) และ `node --test tests/assets.test.mjs` ผ่าน; bundle test ไม่พบ server fixtures/เฉลย
- Playwright บน local: `auth.spec.ts`, `home-design.spec.ts`, `learning-interaction.spec.ts`: **8 passed** รวมสมัครด้วย password 10 ตัวอักษร → login → refresh → logout และหน้าจอ 375/768/1440
- รัน auth lifecycle ซ้ำด้วย password **5 ตัวอักษร**: **1 passed**

พบสาเหตุสมัครไม่สำเร็จจาก API ที่รัน image เก่า: live OpenAPI ยังระบุขั้นต่ำ 12 ขณะที่ UI เปลี่ยนแล้ว จึง rebuild/recreate เฉพาะ API local พร้อม Origin allowlist เดิม แล้ว auth E2E ผ่าน

## ส่วนที่ยังไม่ยืนยัน

Integration tests เฉพาะ password boundaries/legacy login/Google linking จำนวน 6 cases ติดที่ setup ของ `soc-local-test-db-1`: ไม่มี `vector.control` สำหรับ pgvector 0.8.2 จึง **6 setup errors** ก่อนเข้าทดสอบ ไม่แก้หรือ skip assertions เพื่อให้ผ่าน ฐานนี้เป็น `soc_test_foundation` แบบ tmpfs ตาม harness และไม่ใช่ฐานของเว็บ local

ยังไม่ได้รัน full lesson → exam → Instructor review E2E ใหม่ในงานนี้ และยังไม่ยืนยัน GitHub CI, public deployment หรือ real AI/RAG

## สมัครแล้วเข้าสู่ระบบทันที — follow-up หลัง `a5cc495`

ตามคำขอผู้ใช้ล่าสุดวันที่ 21 ต.ค. 2026 `POST /auth/register` ยังคืน 201 `UserEnvelope` แต่สร้าง account/quota/session และ audit ใน transaction เดียว ก่อนออก HttpOnly session cookie และล้าง pre-auth challenge ใช้ session rotation เดียวกับ login หน้าเว็บอ่าน session/CSRF ใหม่แล้วไป `/account` โดยไม่ส่ง password ไป login ซ้ำ ไม่มี migration เพิ่ม

ตรวจบน Python 3.12.14 และ Node 24.20.0 ใน local:

- `ruff check app tests`, `ruff format --check app tests`, `mypy app`: ผ่าน
- `pytest -q -m 'not integration'`: **103 passed, 84 deselected** รวม OpenAPI drift
- `pytest tests/test_auth.py tests/test_google_login.py`: **28 passed** บน Compose project แยก `soc-ci-register-auto` ใช้ PostgreSQL 17.11 + pgvector 0.8.2 และฐาน `soc_test_foundation` แบบ tmpfs ครอบคลุม auto-session, rollback หลัง session insert ล้ม, revoke cookie เดิม, CSRF, password boundaries, legacy login และ Google linking
- Playwright `auth.spec.ts`: **4 passed** บน `127.0.0.1:4175` รวมสมัครแล้วเข้าบัญชีทันที, cookie HttpOnly/SameSite, refresh, logout, stale response และ login ภายหลัง
- Frontend lint/build/TypeScript และ browser asset leakage check: ผ่าน

การใช้ฐานแยกพร้อม image ที่ถูกต้องทำให้ชุด auth integration รันได้; หลังตรวจลบเฉพาะ project `soc-ci-register-auto` และฐาน tmpfs ที่สร้างในงานนี้ ไม่เปลี่ยนหรือลบฐาน `soc-local-test-db-1` ที่ขาด vector ในการตรวจครั้งก่อน API local ของเว็บถูก rebuild ให้ใช้ behavior ใหม่นี้แล้ว ผลยังไม่ใช่การตรวจ GitHub CI หรือ public deployment
