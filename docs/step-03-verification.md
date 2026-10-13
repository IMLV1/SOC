# ผลตรวจข้อ 03 — 13 ตุลาคม 2026

สถานะ: **ผ่าน local และ GitHub CI; branch protection ติดข้อจำกัดแพ็กเกจ**
เริ่มงานบน f1 ที่ 3c952c9 พร้อมงานข้อ 02 ที่ยังไม่ commit; คงงานเดิมไว้ครบ ไม่ switch/reset/stash
ตรวจไม่พบ AGENTS.md; remote HEAD เป็น main ต่อมาผู้ใช้อนุญาต commit/push/PR และตรวจ CI จริง ผลอยู่ด้านล่าง

## ไฟล์ที่เพิ่ม/แก้เฉพาะข้อ 03

- .github/workflows/ci.yml: prototype/backend/frontend/integration/ci-gate, SHA pins, read-only token, report artifacts
- scripts/ci_gate.py และ scripts/tests/test_ci.py: fail-closed result aggregation และ regression
- scripts/ci-compose.sh: disposable Compose project, integration/HTTP smoke และ cleanup ของ project นั้น
- scripts/check-doc-links.py: local Markdown file targets; .gitattributes: shell scripts ใช้ LF
- docs/ci-local.md, ci-cd.md, README/index/checklist และรายงานนี้: วิธีรันและ pending GitHub evidence

ไม่มี API/UI/migration ใหม่ในข้อ 03 เพราะขอบเขตคือ CI ของ implementation ที่มีแล้ว
ไม่เปลี่ยน policy สิทธิ์/คะแนน/providers; full deployment design ใน ci-cd.md เป็นอนาคตตาม checklist 18

## ผลรันจริง

| Check | ผล |
|---|---|
| prototype | node syntax 3 files + 18 tests ผ่าน |
| backend | uv frozen install, Ruff lint/format, mypy ผ่าน; foundation/approved OpenAPI 13 tests ผ่าน |
| gate | 4 unittest methods ผ่าน รวม failure/cancelled/skipped/missing/malformed และ CLI exit codes; needs ครบทุก job |
| workflow | actionlint 1.7.7 checksum verified; syntax/expressions และ bash -n ผ่าน |
| docs | local Markdown file targets ผ่าน |
| frontend | npm ci/lint/typecheck/production build ผ่าน |
| exact CI integration script | Git Bash + Docker Linux Engine, project soc-ci-local03: build/up/migrate ผ่าน |
| PostgreSQL integration | 16 tests ผ่านใน test container, JUnit integration.xml เขียนได้ด้วย non-root |
| HTTP/worker | frontend smoke 3 tests ผ่าน; worker database_ready=true และ queue_ready=false |
| cleanup | script ลบ soc-ci-local03 containers/network/volume แล้ว; soc-local ยังทำงาน; ทดลองชื่อ soc-local ถูกปฏิเสธ exit 2 ก่อนเรียก Docker |
| reports | backend.xml/integration.xml อยู่ใน ignored test-results; GitHub artifact upload ผ่านใน run ที่อ้างอิงด้านล่าง |

Backend มี upstream HTTPX/Starlette deprecation warning เดิม 1 รายการ ไม่ suppress และไม่มี test failure
พบ format mismatch ใน script ระหว่างรอบแรก แก้ให้ใช้ backend Ruff config แล้วตรวจผ่าน
ไม่มี dependency/runtime upgrade หรือเปลี่ยน lockfilesเพิ่มจากงานข้อ 02

## GitHub verification ที่รันจริง

- Commit 3dfb57b เก็บงานข้อ 02/03; 13cbf3a รวม ancestry ของ main ที่เคย revert scaffold โดยคง f1 tree เพื่อให้ PR มีระบบครบ ไม่แก้ main
- [PR #3](https://github.com/IMLV1/SOC/pull/3) f1 → main เปิดไว้ ไม่ merge
- [รอบแรก](https://github.com/IMLV1/SOC/actions/runs/38395949531): prototype/frontend/integration ผ่าน; backend ล้มใน import smoke และ ci-gate ล้มตามจริง
- แก้ import smoke ให้ใช้ alias api (import worker เคย bind ชื่อ app ทับ FastAPI instance) ใน commit 12bedb6; ไม่ใช่ test assertion ที่ถูกลดความเข้มงวด
- [รอบผ่าน](https://github.com/IMLV1/SOC/actions/runs/38396418296), SHA 12bedb63dff11da98e262452bb87650dd68a124b: prototype/backend/frontend/integration/ci-gate success ทั้งหมด รวม setup/cache/artifact steps
- [PR ทดสอบ #4](https://github.com/IMLV1/SOC/pull/4) ใช้ branch แยก ไม่แก้ f1; [run](https://github.com/IMLV1/SOC/actions/runs/38396064683) สั่ง cancel แล้ว conclusion=cancelled, integration=cancelled, ci-gate=failure
- PR #4 มี deliberate failing test แต่ backend หยุดที่ import-smoke bug ก่อนถึง test นั้น จึงไม่อ้างว่า deliberate test ถูก execute; หลักฐาน failure propagation ใช้รอบแรกของ PR #3
- ปิด PR #4 โดยไม่ merge และลบ temporary branch แล้ว; ยังเก็บ run URLs สำหรับตรวจย้อนหลัง
- เจ้าของมี admin permission แต่ GET main/protection และ rulesets ตอบ HTTP 403: "Upgrade to GitHub Pro or make this repository public to enable this feature." ไม่แก้ visibility/ซื้อแพ็กเกจเอง

## ยังไม่ยืนยัน

- fork/merge_group event จริง (workflow รองรับและ syntax ผ่าน แต่ทดสอบครั้งนี้ใช้ PR ใน repo เดียวกัน)
- branch protection/ruleset และ enforced merge blocking เมื่อ failure/cancelled: ติด GitHub plan ไม่ใช่ CI ผ่านแล้วแปลว่า protection เปิด
- ไม่มี domain E2E/generated client, security scan เต็มระบบ, provider หรือ deploy จนกว่าจะถึงงานที่กำหนด

ดู [คำสั่ง local และขั้นตั้ง required check](ci-local.md)
