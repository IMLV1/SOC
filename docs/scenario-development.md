# ข้อ 05 — Training fixtures และ exam boundary

> **เอกสารตามขั้นตอนเดิม:** ไฟล์นี้อธิบายการทำข้อ 05 ตามสถานะตอนนั้น ไม่ใช่คู่มือปัจจุบันครบทุก flow. ข้อความที่บอกว่ายังไม่มี runner/exam/API เป็น snapshot เก่า; ปัจจุบันมี run และ learning/exam implementation บางส่วนแล้ว ให้ดู [checklist](implementation-checklist.md) และรายงานข้อ 15–17 ก่อนใช้อ้างสถานะ

อ่าน [ผลตรวจ](step-05-verification.md), [SRS](srs.md) และ [OpenAPI](openapi.yaml) ร่วมกัน
ข้อ 01 มี scaffold/contracts/lockfiles อยู่แล้ว จึงคง implementation ข้อ 02–04 และ runtime pins เดิม
ขอบเขต implementation ข้อ 05 ตอนนั้นคือ GET /api/v1/scenarios และหน้า /scenarios; ข้อความนี้ไม่ใช่ข้อจำกัดของระบบปัจจุบัน

## Catalog และ fixtures

- catalog seed มี S01–S05 v1 schema เดียวกัน พร้อม normal traffic; เปิด S02 ก่อน
- GET catalog อ่าน PostgreSQL และคืนเฉพาะ id/version/title/difficulty/duration_ms/learning_objectives
- catalog ใช้ cursor UUID เรียงคงที่, limit เริ่ม 50 สูงสุด 100; next_cursor=null เมื่อหมด
- event fixtures เป็น server-only release schedule แยกจาก catalog และ private truth
- demo เดิมเป็น snapshot benign อีกชุด ไม่ใช้ events จาก training หรือ exam
- ยังไม่มีข้อสอบจริงหรือ exam seed: format รองรับ purpose=exam แต่ training loader/seed/table ปฏิเสธ
- S01–S05 มี incident groups/threat labels เพื่อ training evaluation ภายหลัง ไม่ใช่ rubric/เกณฑ์สอบ
- การใช้หลาย scenario/versions ใน run และการนับ quota อยู่ข้อ 06; selector ในข้อนี้ไม่สร้าง run

Migration 0003 เพิ่ม app.scenarios (purpose ต้อง training) และ private.ground_truth
API SELECT ได้เฉพาะ catalog columns ไม่ได้ fixture_hash/seed_hash และไม่มีสิทธิ์เขียน
worker/detector อ่าน truth ไม่ได้; evaluator อ่าน truth ได้แต่เขียน/ลบไม่ได้
ยังไม่มี privileged HTTP truth handler; การเปิดในอนาคตต้องตรวจ state/assignment/audit ตาม SRS

## Seed และการรัน

จาก root หลังสร้าง secrets ตามคู่มือ [local](local-development.md):

```powershell
docker compose up --build -d --wait
docker compose logs seed
docker compose run --rm seed
```

ลำดับคือ bootstrap → migrate → seed → API/worker → UI
seed ใช้ migration_owner และ transaction advisory lock แยก, รันซ้ำหรือพร้อมกันไม่ duplicate
เปลี่ยนเนื้อหาใน version เดิมให้ error/rollback ไม่เขียนทับ; เพิ่ม UUID/version ใหม่สำหรับ revision
รายละเอียด canonical hash อยู่ใน [fixture guide](../backend/fixtures/README.md)
native หลัง migrate: จาก backend ตั้ง owner DB env แล้วรัน `python -m app.scenarios.seed`
คำสั่งไม่พิมพ์ truth, payload, path หรือ credentials เมื่อผิดพลาด

เปิด [catalog](http://127.0.0.1:3000/scenarios) และ [API](http://127.0.0.1:3000/api/v1/scenarios)
หน้า UI แสดง loading/error/retry/empty, version/เป้าหมาย และบอกว่ายังเริ่มรอบไม่ได้
runtime pin/lockfiles/.env.example ใช้ของเดิม ไม่เพิ่ม provider หรือ secret

## Artifact isolation

| Container target | มี fixture ใด | credential |
|---|---|---|
| base/API | ไม่มี | api_runtime เฉพาะ API |
| runner | events/training เท่านั้น | worker_runtime |
| seed | training catalog/events/truth | migration_owner เฉพาะ one-shot |
| test | restricted seed assets สำหรับฐานทิ้งได้ | test role secrets |
| frontend | ไม่มี backend fixtures | ไม่มี DB secrets |

อย่าใช้ seed/test image เป็น runtime API/worker; CI ตรวจ filesystem ของ API/worker/web จริง
ไม่ index docs/fixtures/truth ลง RAG และไม่เปิด directory เหล่านี้ผ่าน static route
local repository เป็น authoring source ที่ operator อ่านได้ ไม่ใช่ security boundary ต่อผู้มีสิทธิ์อ่าน source

## Exam policy ที่ต้องใช้ก่อนเปิด endpoints

project_exam สร้าง allowlist ใหม่จาก scalar/UUID เท่านั้น ไม่ส่ง training DTO แล้วลบ field
run คืน id/mode/status/version/elapsed_ms; alert คืน id/run_id/evidence_ids;
ticket เพิ่ม workflow status/version และ neutral title ที่ server สร้าง ไม่ใช้ชื่อจาก detector
ไม่มี label/rubric/AI hints/initial severity/nested result ทุกสถานะ รวม completed
unknown surface และ events/overview/history/audit/analysis/sources/exports/result/truth ปฏิเสธโดย default
จนกว่าจะมี scoped/released/redacted schema พร้อม tests ใน feature นั้น

นี่เป็น projection policy ไม่ใช่ authorization: handler ต้องตรวจ owner/assignment/released evidence
ก่อนเรียกเสมอ และยังไม่มี exam handler เรียกใช้ในข้อนี้ Instructor truth ต้องหลัง submit + audit;
learner ได้ feedback เท่านั้น; D-01–D-07 ที่ยัง pending ไม่ถูกตัดสินแทน
attempt lifecycle/submit/idempotency/finish และ global locks คง SRS §4–5
training selector รับเฉพาะ UUID ที่ enabled ในตาราง training; ไม่มีทาง query exam bank
POST runs/level attempts ยัง 404; ไม่ถือว่าผ่าน gate end-to-end ของข้อ 16

## ตรวจซ้ำ

```powershell
cd backend
uv run --frozen pytest -m 'not integration'
uv run --frozen python ../scripts/generate-client-types.py --check
cd ../frontend
npm run lint
npm run typecheck
npm run build
node --test tests/assets.test.mjs
cd ..
```

ใช้ Git Bash/Bash: `COMPOSE_PROJECT_NAME=soc-ci-scenarios05 bash scripts/ci-compose.sh`
สร้างฐานทิ้งได้ รัน migration/upgrade/seed/grants/API/HTTP/Chromium แล้วลบเฉพาะ project ทดสอบ
เพิ่ม tests ใน CI เดิมแล้ว; GitHub ของงานข้อ 05 ยังรอยืนยันจน commit/push และรันจริง
