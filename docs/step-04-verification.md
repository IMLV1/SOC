# ผลตรวจข้อ 04 — 14 ตุลาคม 2026

Branch `codex/step-04-auth` สร้างจาก origin/main `56b49a9` หลัง PR #5 merge
ก่อนเริ่ม working tree สะอาด ไม่พบ AGENTS.md; คง prototype และงานข้อ 01–03
ผู้ใช้ยืนยัน registration defaults 10 runs/20 AI requests ต่อวัน UTC แก้เฉพาะการตัดสินใจนี้

## ไฟล์ที่เปลี่ยน

- backend/app/auth: request/response models, session/CSRF/Argon2id, quota/read models, rate limit และ owner/assignment policies
- backend/app/demo.py: public benign snapshot; http_models.py/main.py: shared safe envelopes/routers/errors
- migrations/versions/0002_auth_rate_limits.py: counters/grants โดยไม่แก้ migration 0001 ที่เคยใช้แล้ว
- backend/tests/conftest.py: shared isolated DB fixtures; test_auth.py และ test_database.py: behavior/races/upgrade
- frontend/src/app: login/register/account/demo และ session-aware navigation; lib: API fetch และ generated DTOs
- frontend/tests/browser/auth.spec.ts, playwright.config.ts, package.json/package-lock.json: Chromium regression
- compose.yaml/backend env/Dockerfile, CI workflow/script: local cookie/origin config และ auth/browser tests
- docs/openapi.yaml, SRS/API/architecture, checklist/คู่มือ และ type-generation script

## ผลตรวจจริง

| Check | ผล |
|---|---|
| PostgreSQL integration | 26 passed: DB เดิม 16 + auth 9 + upgrade จาก 0001 อีก 1 |
| Auth | register ไม่ auto-login; normalized email; role/quota injection ถูกปฏิเสธ; login failure generic; opaque/hash-only session; rotation/logout |
| Security regression | Origin/CSRF/replay/expired challenge; session expiry/revoke/disabled; Secure/HttpOnly/SameSite; 429 หลัง failed attempts |
| Isolation | /me เลือกบัญชีจาก cookie ไม่ใช้ query user_id; owner mismatch 404; Instructor นอก assignment 404; Analyst admin policy 403 ผ่าน api_runtime |
| Concurrency/upgrade | สมัคร email เดียวพร้อมกันได้ 201/409 และมี user/quota/audit อย่างละ 1; upgrade เก็บบัญชีจาก 0001 |
| Foundation/contract | 13 passed; approved FastAPI paths/schema เทียบ OpenAPI และ draft exam allowlists ยังผ่าน |
| Browser Chromium | 2 E2E ผ่าน: register→login→refresh→logout ผ่าน Next.js proxy; stale session response ไม่ทำให้ UI กลับมา login หลัง logout; Guest demo read-only; widths 375/768/1440 ไม่ overflow |
| HTTP smoke | 3 passed; assets/proxy และ domain routes ที่ยังไม่ implement ยัง unavailable |
| Build/static | Docker Next standalone build, frontend lint/typecheck, backend Ruff/format/mypy และ actionlint ผ่าน |
| CI scope | เพิ่ม auth integration, Chromium และ generated DTO drift checks; **ยังไม่รัน GitHub CI สำหรับ branch ข้อ 04** |

Backend ยังมี upstream HTTPX/Starlette deprecation warning เดิม ไม่ suppress
ชุด integration/CI ใช้ project soc-ci-auth04 และฐานแยก ไม่แตะข้อมูลผู้ใช้จริง
การตรวจข้ามบัญชีเป็น account projection และ authorization policy ของข้อ 04;
ยังไม่อ้างว่า run/ticket/admin endpoints ที่ไม่มีอยู่ถูกทดสอบแล้ว

## ยังไม่พร้อม / นอกขอบเขต

ยังไม่มี scenario/runner, lessons/exam, admin CRUD, email verification/password reset, provider หรือ public deployment
ส่วน demo ticket/alert/evaluation ยัง draft; ข้อนี้ให้ตัวอย่างอ่าน request/response เท่านั้น
Production ต้องใช้ HTTPS Secure cookies, trusted proxy/rate-limit policy และ retention scheduler ตามงานถัดไป
branch protection ยังติด GitHub plan เดิม; ไม่เปลี่ยน billing/visibility
งานข้อ 04 เตรียมส่ง PR เพื่อตรวจ GitHub CI; ยังไม่ deploy; วิธีเปิดและคำสั่งตรวจอยู่ใน [คู่มือ auth](auth-development.md)
เปิด preview project soc-auth04 แยกที่ localhost:13004 (API 18004, DB 55434); ไม่มี provider จริง
