# ผลตรวจข้อ 01 — 13 ตุลาคม 2026

Branch `f1` คงเดิม; HEAD ก่อนเริ่ม `1170066`. ไม่ commit/เปลี่ยน branch/deploy
งานเดิมที่พบ: `docs/README.md` modified และ `docs/implementation-checklist.md` untracked
เก็บเนื้อหาเดิมไว้และเพิ่มผลข้อ 01; ไม่แก้ `prototype/`. ไม่พบ AGENTS.md ใน repository/parent ที่ตรวจ

## สิ่งที่เพิ่ม

- `docs/srs.md`: gaps/conflicts, FR/NFR/use cases/mapping, ER/data deltas,
  training/exam serializer policy, lifecycle/finish/submit, global lock order และ decision register
- `docs/openapi.yaml`: 81 operations (health approved 2, domain draft 79),
  request/response foundations, closed exam views และ requirement IDs;
  domain payload/filter details ที่ยังไม่ครบติดป้าย draft ชัดเจน
- `frontend/`: Next.js App Router/TypeScript landing page, CSS, same-origin proxy,
  standalone build/start scripts, smoke tests, exact package pins/lockfile/env example
- `backend/`: FastAPI health/error envelopes, Python worker entrypoint,
  pinned DB libraries/Alembic, uv lockfile/env example และ foundation/contract tests
- ปรับ API/architecture/database/learning/RAG/scope/index และ root README ให้เชื่อม contract ใหม่
  เพิ่ม runtime version files และ Python/tool cache ignore rules

## ผลที่ตรวจจริง

| Check | ผล |
|---|---|
| npm dependency install/audit | ผ่าน; ชุดสุดท้าย 0 vulnerabilities ใน npm audit |
| npm ci จาก lockfile | ผ่าน (ดูหมายเหตุ runtime ด้านล่าง) |
| uv sync --frozen | ผ่าน; dependencies 50 packages |
| Frontend ESLint / TypeScript | ผ่าน |
| Next.js production build + standalone static assets | ผ่าน |
| FastAPI Uvicorn startup | ผ่านบน 127.0.0.1:8000 |
| Standalone frontend startup | ผ่านบน 127.0.0.1:3000 |
| Backend Ruff check/format + mypy | ผ่าน |
| FastAPI/SQLAlchemy/asyncpg/Alembic import | ผ่าน; ไม่ใช่ DB integration |
| OpenAPI 3.1 validation + approved drift/inventory mapping | ผ่าน |
| pytest | 13 passed; รวม health/error, draft route not exposed, worker exits, contract และ schema leakage guards |
| Frontend HTTP smoke | 3 passed; HTML/JS assets, health 200/ready 503 ผ่าน proxy, domain POST 404 |
| Prototype regression | 18 passed; ไม่แก้ไฟล์ prototype |
| Browser inspection | Edge ผ่าน Playwright runtime ของเครื่อง: 375/768/1440px ไม่มี horizontal overflow, keyboard focus เห็นได้, ไม่มี pageerror; ตรวจ screenshot 375/1440 แล้ว |
| git diff --check | ผ่าน; prototype ไม่มี diff |

Windows sandbox เริ่มต้นทำให้ SWC canonicalize path ไม่ได้และ TestClient ค้าง;
ตรวจซ้ำด้วย approved local execution แล้ว build/tests ผ่าน โดยไม่ได้ลด assertions
Playwright bundled Chromium ไม่มี binary จึงใช้ Edge ที่ติดตั้งอยู่; browser check เป็นการตรวจ local
ครั้งนี้ ไม่ใช่ committed E2E suite หรือหลักฐาน full responsive acceptance ของระบบทั้งหมด
HTTP smoke tests อยู่ใน repository และรันซ้ำตาม getting-started ได้

Starlette test client แจ้ง deprecation เมื่อใช้ HTTPX 0.28.1 (แนะนำ httpx2 ใน upstream รุ่นที่ติดตั้ง)
tests ยังผ่าน; ไม่ suppress warning และยังไม่เปลี่ยน stack HTTPX ตาม docs ในข้อ 01

## สิ่งที่ไม่พร้อม / ไม่ได้อ้างว่าทดสอบแล้ว

DB readiness ตอบ 503 โดยตั้งใจ; ไม่มี DB connection/schema/migration/roles/Compose
หรือ PostgreSQL version/image ที่เลือกแล้ว ไม่มี auth/runner/durable worker/job recovery,
exam/grading/unlock/RAG/real provider, CI/deployment/backup หรือ benchmark จริง
exam allowlist tests ตรวจ draft JSON schema เท่านั้น ไม่ใช่หลักฐาน runtime exam security
ไม่มี default secret หรือ fixture/answer key ถูกคัดลอกเข้า frontend; การตรวจ bundle เป็น smoke
guard ร่วมกับการตรวจ source ไม่ใช่ security scan ครบทั้ง supply chain

ผู้ใช้ยืนยัน policy: Instructor อ่านเฉลยสอบหลัง submit เท่านั้น; learner ได้เฉพาะ rubric feedback
rubric/เกณฑ์ผ่าน, active/retake/expiry policy, override/revoke unlock, feedback disclosure detail,
provider/model/งบ และ hosting ยัง pending ตาม SRS §8
ข้อ 01 ผ่านในฐานะ **contract draft + scaffold** ไม่เท่ากับ SOC-001/002 ทุก phase เสร็จ
หรืออนุญาตให้ทำข้อ 02–19 ต่อโดยอัตโนมัติ
