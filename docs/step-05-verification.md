# ผลตรวจข้อ 01 ทบทวน / ข้อ 05 — 14 ตุลาคม 2026

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


เริ่มจาก working tree สะอาดบน codex/step-04-auth; fetch แล้ว main เป็น 6a51b51 หลัง PR #7 merge
สร้าง branch codex/step-05-scenarios จาก main เพื่อแยกงานใหม่ ไม่แก้ prototype/หรือลดงานข้อ 02–04
ไม่พบ AGENTS.md; อ่าน docs รวม learning-path/RAG และตรวจ contract inventory ก่อนแก้

## ทบทวนข้อ 01

SRS/OpenAPI/mapping, App Router/TypeScript, FastAPI/worker, runtime pins, lockfiles,
.env.example และ health มีอยู่แล้ว คงเวอร์ชันที่ตรวจจริงไว้ ไม่สร้าง scaffold ทับ
แก้ข้อความสถานะล้าสมัยที่ยังบอกว่าเปิด health เท่านั้น/ยังไม่มี auth/DB
boundary/lifecycle/finish-submit/lock order ยึด SRS; ไม่มีการเปลี่ยนสิทธิ์/คะแนน/ผลิตภัณฑ์
rubric, retake/active attempt, override/revoke unlock, feedback disclosure, provider และ hosting ยัง pending

## ขอบเขตข้อ 05

เพิ่ม scenario models/loader/seed/catalog/exam policy, migration 0003,
S01–S05 training fixtures + private truth, Docker artifact separation,
catalog UI/generated DTO และ regression tests/CI พร้อม [คู่มือ](scenario-development.md)
S02 เปิดใน catalog; อีก 4 แบบเตรียม schema/events/truth แต่ยัง disabled
ไม่สร้าง jobs/run controls/detector/exam bank/grading/provider/deploy

## ผลตรวจ

| Check | ผลที่รันจริง |
|---|---|
| Foundation/contract/fixture policy | 20 passed; OpenAPI valid, approved paths/schema drift, draft route denial และ exam projection tests |
| PostgreSQL integration | 30 passed บน roles จริง รวม auth/DB เดิม; fresh migration, upgrade จาก 0001 และ 0002 รักษาบัญชี |
| Container test command | 37 passed = integration 30 + fixture/policy unit 7 (unit 7 ซ้ำกับชุด 20; รวม backend ไม่ซ้ำ 50) |
| Seed | 5 versions/10 groups, repeat/concurrent ไม่ duplicate; conflict rollback; exam purpose ปฏิเสธที่ loader/seed/DB |
| Grants/admission | API/worker SELECT truth ไม่ได้; evaluator อ่านได้แต่แก้ไม่ได้; API อ่าน hashes/เขียน catalog ไม่ได้; disabled/unknown/demo UUID ไม่ผ่าน training selector |
| API/errors | catalog มีแต่ allowlisted metadata, cursor/limit validation และ pagination ไม่ซ้ำ; fixture paths 404, run/attempt creation ยัง 404; errors ไม่ echo input |
| Artifact isolation | container API ไม่มี fixtures, worker มีเฉพาะ training events ไม่มี catalog/truth, web ไม่มี backend; browser JS ทุกไฟล์ผ่าน leakage test 1 |
| HTTP/worker | smoke 3 passed; database_ready=true, queue_ready=false |
| Browser | Chromium E2E 4 passed: auth/Guest เดิม + catalog ที่ 375/768/1440 ไม่มี overflow + loading/error/retry/empty |
| Static/build | Ruff lint/format (38 files), mypy (23 source files), frontend lint/typecheck/standalone build, actionlint, doc links, DTO drift และ gate regression 4 ผ่าน |
| Reproducibility | uv sync --frozen --offline ผ่าน; runtime/package lockfiles เดิมไม่เปลี่ยน; Docker build ใช้ pinned images/dependencies |
| CI local | scripts/ci-compose.sh exit 0 ใน project soc-ci-scenarios05, cleanup เฉพาะ test project/volume สำเร็จ |

ยังมี upstream HTTPX/Starlette deprecation warning เดิม ไม่ suppress และไม่ลด assertions
prototype ไม่มี diff; ไม่อ้างว่ารัน prototype regression ใหม่ในข้อนี้

## เปิดตรวจและสิ่งที่ยังไม่พร้อม

Preview แยก project soc-scenarios05: [catalog](http://127.0.0.1:13005/scenarios),
[API](http://127.0.0.1:13005/api/v1/scenarios), API port 18005, DB port 55435
เปิดซ้ำด้วย SOC_WEB_PORT=13005, SOC_API_PORT=18005, SOC_DB_PORT=55435 แล้ว
`docker compose -p soc-scenarios05 up --build -d --wait`; หยุดด้วย down โดยไม่ลบ volume

ข้อ 05 ผ่าน local acceptance; เพิ่ม regression tests ใน CI แล้ว แต่ **รอยืนยันบน GitHub**
ยังไม่ commit/push งานข้อ 05 ไม่ deploy ภายนอกและไม่เปิด provider
exam policy ตรวจเฉพาะ helper + schema/route denial ไม่ใช่ end-to-end exam/lesson gate ที่ยังไม่มี
S01/03/04/05 ยัง disabled; detector acceptance อยู่ข้อ 08, runner อยู่ข้อ 06
rubric/retake/unlock/provider ตาม decision register ยัง pending และ branch protection ยังติดแพ็กเกจเดิม
