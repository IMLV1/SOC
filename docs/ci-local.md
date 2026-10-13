# CI ข้อ 03 — วิธีตรวจและเปิดใช้ required check

Workflow อยู่ที่ [.github/workflows/ci.yml](../.github/workflows/ci.yml)
local commands/config ผ่านแล้ว; **รอยืนยันบน GitHub** ยังไม่ได้ push, รัน Actions หรือเปลี่ยน branch protection
ผลตรวจอยู่ใน [step-03-verification.md](step-03-verification.md)

## ขอบเขตที่ implement

| Job | Checks |
|---|---|
| prototype | syntax 3 files และ model tests 18 cases; ไม่แก้ prototype |
| backend | frozen uv, Ruff lint/format, mypy, foundation tests, OpenAPI validation/approved schema drift, Python import, Markdown file links, gate regression, actionlint และ Bash syntax |
| frontend | npm ci, ESLint, typecheck, Next.js standalone build |
| integration | Compose Linux image build/start, fresh DB migration, real role/transaction tests, HTTP frontend smoke และ worker readiness |
| ci-gate | ต้องได้รับ success จากทุก job; failure/cancelled/skipped/missing/malformed ถูกปฏิเสธ |

ทุก PR และ push main รันทั้งหมด รวม docs-only; มี merge_group และ manual dispatch
ตรวจ remote default branch แล้วเป็น main ไม่ใช้ path filters, continue-on-error หรือ pull_request_target
ci-gate มี always() และ needs ครบทุก job; tests ตรวจว่าเพิ่ม job แล้วต้องเพิ่ม gate dependency ด้วย
หากยกเลิกทั้ง workflow จน gate เริ่มไม่ได้ ผล cancelled/pending ต้องยัง block merge เมื่อ required check ตั้งถูกต้อง

Actions pin full commit SHA จาก official repository tags; checkout ไม่เก็บ credential
permissions เป็น contents:read ไม่มี deploy/provider/registry secrets หรือ write token
Node 24.20.0, npm 11.19.0, Python 3.12.14, uv 0.9.5 ตรง local; cache ผูก lockfile
actionlint 1.7.7 download ตรวจ SHA-256; ตรวจ workflow syntax/expressions โดยปิด optional ShellCheck
Bash ตรวจด้วย bash -n และรัน script จริง; ไม่อ้างว่าได้ตรวจ ShellCheck
Markdown checker ตรวจ local inline file targets เท่านั้น ไม่ตรวจ URL ภายนอกหรือ heading anchors
JUnit backend/integration upload 14 วัน เฉพาะ test-results/*.xml ไม่ upload .local, logs, cookies หรือ secrets

CI ทดสอบเฉพาะพฤติกรรมที่มีในข้อ 01–02; ไม่มี generated TypeScript client/domain E2E ในขั้นนี้
approved FastAPI contract เปรียบเทียบกับ OpenAPI แล้ว ส่วน domain schemas ยัง draft
PostgreSQL 17.11 เป็น local baseline เดิม; production/pgvector compatibility รอยืนยันในงานภายหลัง
เพิ่ม regression tests สำหรับ feature ใหม่ใน jobs เดิมต่อไป ไม่ใช้ stub test อ้างว่า auth/exam/runner ผ่านแล้ว

## รัน local

จาก root ใช้ runtimes ตาม pin และติดตั้ง backend/frontend dependencies ก่อน:

```powershell
node --check prototype/app.js
node --check prototype/model.js
node --check prototype/server.cjs
npm --prefix prototype test
cd frontend
npm ci
npm run lint
npm run typecheck
npm run build
cd ../backend
uv sync --frozen
uv run --frozen ruff check app tests migrations ../scripts
uv run --frozen ruff format --check app tests migrations ../scripts
uv run --frozen mypy app
uv run --frozen pytest -m 'not integration' --junitxml=../test-results/backend.xml
uv run --frozen python ../scripts/check-doc-links.py
uv run --frozen python -m unittest discover -s ../scripts/tests -v
cd ..
python scripts/init-local.py
```

เปิด Docker Linux engine แล้วรันใน Bash จาก root (Windows ใช้ Git Bash):

```bash
COMPOSE_PROJECT_NAME=soc-ci-local03 bash scripts/ci-compose.sh
```

สคริปต์ยอมรับเฉพาะ project ที่ขึ้นต้น soc-ci- และมี suffix;
ใช้พอร์ต 18000/13000/55438 เพื่อแยก soc-local 8000/3000/55432
กำหนด SOC_API_PORT/SOC_WEB_PORT/SOC_DB_PORT อื่นถ้าซ้ำ
เลือกชื่อ project ใหม่ที่ไม่มีข้อมูลต้องเก็บ: script ลบ containers/network/volumes ของ project นั้นเมื่อจบ
ไม่ใช้ชื่อ soc-local; test-db เป็น tmpfs แยกจากฐาน app ใน CI อีกชั้น
ไฟล์ secrets สุ่ม local เก็บเดิม; บน GitHub runner สร้างใหม่จาก checkout ทุกครั้ง
reports ถูกเขียนโดย container non-root; test-results เป็น ignored output และไม่ควรเก็บข้อมูลจริง

## ตั้ง required check บน GitHub (ยังไม่ได้ทำ)

1. Push งานนี้และเปิด PR เข้า main เมื่อผู้ใช้สั่ง แล้วตรวจ jobs ทุกตัวบน GitHub-hosted ubuntu-24.04
2. ที่ repository Settings → Rules → Rulesets (หรือ Branch protection) ตั้ง target main
3. บังคับ Pull Request/review และ Require status checks to pass; เลือก check ชื่อ **ci-gate** จาก GitHub Actions หลังมี run แรก
4. เปิด Require branches to be up to date หรือใช้ merge queue ตามนโยบาย repository; workflow รองรับ merge_group แล้ว
5. ตรวจด้วย PR ทดสอบที่ test fail ว่า merge ถูกกัน และ PR ที่ผ่านได้รับ gate success; ทดสอบ cancelled run ด้วย
6. ถ้า plan/สิทธิ์ repository ไม่รองรับ ruleset ที่เลือก ให้บันทึก limitation ห้ามรายงานว่า protection เปิดแล้ว

อย่าใช้ผล local แทนหลักฐาน GitHub run/merge protection; manual gate test ไม่ได้ตั้ง protection ให้ repository
ไม่มี release.yml, maintenance หรือ deployment adapter ในข้อ 03

อ้างอิง [GitHub required checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)
และ [workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
