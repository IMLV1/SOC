# ผลตรวจข้อ 06–10 (อัปเดต 15 ตุลาคม 2026)

## Audit ล่าสุด — สถานะนี้มีผลเหนือรายงานรับงานเดิมด้านล่าง

### ปิด acceptance ข้อ 08 — 14 ตุลาคม 2026

- Rules/anomaly/correlation v2 ตรึง config ไว้ใน `run_versions`; run ที่ตรึง v1 ยังคงใช้ policy v1 เพื่อรักษาผลย้อนหลัง
- Rules ใช้ failed login ≥10/5 นาที, scanner ≥4/5 นาที และแสดง blocked request เป็นหลักฐาน low severity โดยไม่สรุปว่าถูกเจาะ
- Anomaly ใช้ baseline ที่ปล่อยแล้ว, อย่างน้อย 3 read events ใน 60 วินาที และ ≥8 เท่าของ baseline (`baseline_reads_per_minute × 100 records/read`); S05 สร้าง anomaly จริง
- Correlation จำกัด scenario instance/account/session/asset/time; detector query อ่านเฉพาะ released events ของ run นั้น
- Integration tests ส่ง duplicate detection jobs สองงานซ้ำแล้ว detection/alert/automatic ticket ไม่เพิ่ม; เมื่อ S05 มีหลักฐานใหม่หลัง soft-delete จะได้ detection/alert revision ใหม่ที่ผูก ticket เดิม ไม่มี ticket ซ้ำ และ FK ปฏิเสธ detection/ticket evidence ข้าม run
- Chromium E2E บน S02 รอ alert และ automatic ticket ที่สร้างจาก PostgreSQL จริง; alerts แสดง severity, version, explanation, evidence count และ link ไป ticket
- Normal traffic และ fixtures S01–S05 ผ่าน unit cases; blocked request ไม่ถูกตีความเป็น successful compromise
- ผล local: integration 45 passed, HTTP smoke 3 passed, Chromium 9 passed; หลังเพิ่ม S05 PostgreSQL flow และปรับ correlation ล่าสุด รัน duplicate-job/S05 integration ซ้ำ 2 passed. Unit detector 2 passed, Ruff, mypy 50 modules, generated DTO drift, frontend lint/typecheck และ diff check ผ่าน
- รอบ Docker full CI ถัดจากเพิ่ม S05 test ติดดาวน์โหลด dev dependencies จึงยุติและล้าง project; S05 กับ duplicate-job tests รันแยกบน PostgreSQL disposable แล้วผ่าน. GitHub CI ของ working changes ยังรอยืนยัน

### Acceptance runner continuity ที่รันจริงเพิ่มเติม

14 ต.ค. 2026: `node frontend/tests/runner-continuity.cjs` exit 0
บน Compose soc-accept06 แยก UI/API/DB ports 13006/18006/55436
Chromium สมัคร/login บัญชี synthetic แล้ว POST S02 ผ่าน same-origin API (201)
run_id 7bbb7378-6032-409c-bcfa-7badd03dad1a:

| จุดตรวจ PostgreSQL | สถานะ | Events | Unique event keys / release_seq | Jobs / unique dedupe keys |
|---|---|---|---|---|
| เริ่ม S02 | running | 1 | 1 / 1 | 3 / 3 |
| หลัง logout 204 และ /me 401 | running | 2 | 2 / 2 | 5 / 5 |
| หลังปิด Chromium ทั้ง process | running | 3 | 3 / 3 | 7 / 7 |
| หลัง restart worker จน schedule จบ | reviewing | 15 | 15 / 15 | 37 / 37 |

**เกณฑ์ย่อย API→released events, logout/browser close ไม่หยุด runner และ restart ไม่ซ้ำผ่านจริง**
ไม่ได้เร่ง/แก้ elapsed clock ใน DB; ไม่สร้าง evaluation score
JSON หลักฐาน local อยู่ ignored test-results/runner-continuity.json ไม่มี passwords/cookies/key
คำสั่งตรวจซ้ำต้องเปิด disposable project soc-accept06 ตาม ports นี้ก่อน และตั้ง SOC_DOCKER_BIN
ถ้า Docker CLI ไม่อยู่ PATH; script สร้างบัญชีทดสอบใหม่ทุกครั้ง ไม่ใช้ production
ผล continuity ครั้งแรกนี้ถูกตรวจซ้ำกับ worker ที่แก้ fencing แล้วตามหลักฐานเพิ่มเติมด้านล่าง

ตรวจโค้ด HEAD 2cc275f พร้อม working changes ที่ยังไม่ commit
local CI รอบล่าสุด soc-ci-pending1113: PostgreSQL integration 39 ผ่าน, HTTP smoke 3 ผ่าน,
Chromium E2E 5 ผ่าน รวม run start/evidence/pause/refresh/resume และ 375/768/1440
จึงยืนยัน Playwright CLI ได้แล้ว; ข้อความเดิมที่บอกว่ายังไม่รันเป็นประวัติ
รอบ audit นี้ backend non-integration 37 ผ่าน (รวม foundations งานถัดไป), Ruff/format/mypy,
approved OpenAPI/schema และ generated DTO drift ผ่าน; frontend lint/typecheck ผ่าน
ไม่ได้อ้างว่ารัน GitHub CI ของ working changes แล้ว

| ข้อ | ผลตรวจรับปัจจุบัน | ช่องว่าง |
|---|---|---|
| 06 | ผ่าน local acceptance หลังแก้ | เพิ่ม test_worker_fencing.py ตรวจ contention จริงทั้งสองลำดับ, expired/reclaimed lease, stale analysis result และ transaction rollback; ทุก domain handler จับ run ก่อน job/resource; recovery แยกจาก claim |
| 07 | Local vertical slice ผ่าน | Chromium CLI start/evidence/pause/refresh/resume/responsive ผ่านจริง; ไม่ใช่ acceptance ระบบทั้งหมดหรือผล GitHub ของ working changes |
| 08 | ผ่าน local acceptance ตามผลตรวจล่าสุดด้านบน | Run ใหม่ใช้ rules-v2/baseline-v2/correlation-v2 และ frozen config; integration, anomaly S05, duplicate jobs, cross-run FK และ UI alert ผ่าน local; GitHub CI รอยืนยัน |
| 09 | ผ่าน local acceptance ตามผลตรวจล่าสุดด้านล่าง | disposition คง 3 ค่า (`true_positive`, `false_positive`, `undetermined`) ตามข้อสรุปผู้ใช้; `benign_positive` ยังไม่เปิดเพราะ scoring contract ยังไม่กำหนด |
| 10 | Mock และ real local acceptance ผ่าน; Gemini Free Tier S02 Chromium E2E และ migrations 0008–0009 วันที่ 15 ต.ค. | PostgreSQL timeout/invalid output/retry/quota/citation/evidence tests ผ่าน; global token/cost caps, 429 policy และ experiment C ยัง pending |

Audit แรกปรับ 06/08/09 เป็น pending; หลังแก้และตรวจเพิ่ม 06/08 ผ่าน local และข้อ 09 ผ่าน local acceptance ตามข้อสรุป disposition ล่าสุด; 07/10 คง local acceptance
ผล tests ผ่านไม่ใช้แทนการตรวจ requirement coverage และไม่ปรับกฎ/คะแนนแทนผู้ใช้ใน audit นี้

กิ่ง `codex/steps-06-10` เริ่มจาก `origin/main` ล่าสุด ณ วันที่ทำงานนี้ ไม่แตะ `prototype/` และไม่ deploy/push ภายนอก การทดสอบฐานข้อมูลใช้ `test-db` แบบ tmpfs; การทดสอบ UI ใช้ Compose project แยก `soc-verify-steps` บน loopback 4300/8400/55433 ไม่ใช้ฐานข้อมูลของ project เดิม

## ผ่านและตรวจรับแล้ว

- **06:** Alembic 0004 สร้าง runs/instances/versions/events/jobs/idempotency; worker ใช้ PostgreSQL clock, lease, fencing, retry สูงสุด 3 ครั้ง และ recovery ของ run ที่ไม่มี wake-up. Integration ทดสอบ start พร้อมกัน, idempotency/quota, crash ก่อน/หลัง domain commit, pause/resume และ resume ที่ยังไม่มี event ใหม่. Browser login แล้วเริ่ม S02 จริง, logout และ restart worker: run เดิมจบ schedule เป็น `reviewing`, มี 15/15 released events และ release_seq ซ้ำ 0. `finish` คงสถานะ `completing` พร้อม cutoff/job; ยังไม่มีผลคะแนน เพราะ evaluator เป็นข้อ 11.
- **07:** Next.js run list/start และ Event explorer ใช้ API จริง มี polling/backoff, source filter, after_seq/cursor และ request/response/log แสดงเป็น escaped text. Chromium Playwright CLI เดิน login → start S02 → อ่าน event → pause → refresh → resume และตรวจ viewport 375/768/1440 ว่าไม่มี horizontal overflow; รอบล่าสุด flow เดียวกันเปิด real provider และเห็น analysis สำเร็จ.
- **08:** Alembic 0005 และ worker detector สร้าง versioned rule/anomaly/correlation, evidence, alert และ automatic ticket. Tests ครอบ S01–S05, normal page view, S05 anomaly, blocked request ไม่สรุป compromise สำเร็จ, rerun detector ไม่เพิ่ม detection และ soft-deleted automatic ticket ไม่ถูกสร้างซ้ำ. DB composite FK ปฏิเสธ evidence ข้าม run. Browser S02 เห็น alert/ticket/mock analysis จากข้อมูลที่ปล่อยจริง.
- **09:** Alembic 0006 เพิ่ม Ticket/Note CRUD, assessment revisions, note versions/evidence, audit และ expected_version. PostgreSQL integration 6 tests ครอบ owner/Instructor assignment และ Instructor PATCH, cross-run refs, deleted parent, 409 version conflict, completing read-only, ticket timeline และ filters/cursor. Playwright E2E ผ่านบน Compose แยก: สร้าง manual ticket จาก event จริง, เปิดสองแท็บให้เกิด 409 โดย draft ยังอยู่หลัง refresh latest, สร้าง assessment revision, เลือก note evidence และยืนยัน edit history. Ticket API/OpenAPI ใช้ disposition 3 ค่า (`true_positive`, `false_positive`, `undetermined`) ตามข้อสรุปผู้ใช้; `benign_positive` ยังไม่เปิดเพราะ scoring contract ไม่ได้กำหนดผลไว้.
- **10:** Alembic 0007–0009 เพิ่ม analysis/provider mode, frozen evidence refs, attempts, async job, citation subset validation, quota reservation/reconciliation, GET/retry และ list filter/cursor; migration 0008 ถอนสิทธิ์ worker แก้ released events และ 0009 อนุญาต pin `real`. Mock deterministic tests ยังผ่าน. Gemini Free Tier adapter ใช้ Gemini 3.5 Flash-Lite เฉพาะ synthetic S02; structured output ผ่าน Pydantic/citation validation, usage tokens ถูกบันทึก และ malformed response ที่มี usage ถูกคิด quota. timeout ของ real provider คง reservation `unknown`. Chromium E2E ผ่าน login → S02 → real analysis `succeeded` → event explorer → pause/resume; DB ยืนยัน mode/model `real`/`gemini-3.5-flash-lite`, usage 2,615 tokens และ reservation consumed. key อยู่ Docker secret ที่ mount ให้ worker เท่านั้น; frontend ไม่มี secret. PostgreSQL/unit 76 passed, foundation/contract 13 passed, Ruff/format/mypy 51 modules, frontend lint/typecheck, Linux production build และ real E2E 1 passed. GitHub CI ของ working changes รอยืนยัน; ข้อ 12 ยังไม่ผ่าน global caps/429/experiment C และข้อ 13 RAG/embedding ยัง pending.

## ยังไม่พร้อมหรือยังไม่ได้ตรวจ

- Investigation Playwright E2E รันผ่านบน Compose แยกโดยใช้ Chrome ที่ติดตั้งในเครื่องผ่าน `PLAYWRIGHT_EXECUTABLE_PATH`; ใช้ config เดิมของ CI ได้โดยไม่ตั้งตัวแปรนี้เมื่อมี browser ของ Playwright ติดตั้งแล้ว.
- ณ เวลาตรวจข้อ 06–10, `finish` ยังรอ evaluator จึงไม่มี evaluation snapshot; งานนี้เสร็จในข้อ 11 ตาม [ผลตรวจแยก](step-11-verification.md). RAG/embedding, experiment C และ global token/cost controls ยัง pending.
- ยังไม่ได้ deploy, publish, push หรือเปิด paid provider. Compose verification stack เป็น local loopback/ฐานข้อมูลแยกเท่านั้น; real request ที่ทำใช้ synthetic data บน Free Tier ที่ผู้ใช้ยืนยัน.

## คำสั่งตรวจซ้ำ

1. `python3 scripts/init-local.py` (สร้าง secrets เฉพาะเมื่อยังไม่มี)
2. `docker compose --profile test up -d test-db`
3. `docker compose --profile test run --rm test` (หลัง build test image ใหม่)
4. `docker compose build frontend` และ `docker run --rm soc-frontend-check:local npm run lint` หลัง build stage image สำหรับ lint
5. `docker run --rm -v "$PWD:/repo:ro" -w /repo/backend -e PYTHONPATH=/repo/backend soc-local-test:latest python -m pytest tests/test_foundation.py -q -p no:cacheprovider`
6. สำหรับเว็บจริงใช้ Compose project/ports แยก เช่น `SOC_DB_PORT=55433 SOC_API_PORT=8400 SOC_WEB_PORT=4300 docker compose -p soc-verify-steps up -d --build` แล้วเปิด `http://127.0.0.1:4300/runs` (อย่าใช้ project/ports นี้พร้อมข้อมูลเดิมโดยไม่ตรวจ).

ผลล่าสุดก่อน audit ข้อ 10: backend integration **48 passed**, foundation/contract **13 passed** และ generated API types `--check` ผ่าน; Ruff, Mypy, Next.js production build, frontend lint และ HTTP smoke **3 passed**. รอบยืนยันข้อ 10 นี้รัน pipeline integration **7 passed**, unit **4 passed**, Chromium S02 E2E **1 passed**, frontend lint/typecheck และ production build ผ่าน. มีเพียง warning ของ Starlette/TestClient dependency ที่ไม่ทำให้ test ล้ม. Auth rate-limit test ตรึงเวลาใน test เพื่อไม่ให้ข้าม bucket ระหว่างนาที.

## จุดไม่ตรงกันใน docs และข้อสรุปที่ใช้

`database.md` §migration outline ยังเรียก events/detection ว่า revision `003` แต่ revision `0003_scenario_catalog` ถูกใช้ไปแล้วในข้อ 05. จึงต่อ Alembic เป็น `0004`–`0007` แบบ append-only ไม่แก้ migration เดิม; ควรปรับ outline ให้ตรงกับ migration ที่ใช้งานจริงในรอบเอกสารต่อไป. `api.md` ระบุ list filters/cursor และ timeline กว้างกว่าข้อความย่อใน checklist; รอบนี้ implement และทดสอบส่วนของข้อ 09/10 ที่เกี่ยวข้อง แทนการตัด contract. ไม่มีการเลือกเปลี่ยนสิทธิ์/คะแนน/ขอบเขตผลิตภัณฑ์เอง.

## ปิด acceptance ข้อ 06 — 14 ตุลาคม 2026

- เปลี่ยน app/worker/jobs.py และ fencing.py: run lock ก่อน job; recovery แยก transaction จาก claim; settle/heartbeat ปฏิเสธ expired token
- detection/analysis worker ตรวจ lease ก่อนเขียนและก่อนจบ domain transaction; analysis provider call อยู่นอก transaction
- test_worker_fencing.py เพิ่ม 6 integration cases: pause-first/release-first contention ตรวจด้วย pg_stat_activity; expired/replaced worker; stale analysis output หลัง network; rollback เมื่อ lease หมดกลาง transaction
- Local CI soc-ci-fencing06 exit 0: PostgreSQL integration 45 passed, HTTP smoke 3 passed, Chromium E2E 5 passed และ cleanup test project สำเร็จ
- Foundation/non-integration 37 passed; Ruff lint/format (76 files), mypy (49 source files), approved OpenAPI/DTO/doc links ผ่าน
- continuity ซ้ำกับ worker ใหม่ run bef6f55a-bf72-4586-886f-c417f587eba5: start 2 events → logout 3 → ปิด Chromium process 4 → restart worker จบ reviewing 15/15 unique events/release_seq, 37/37 unique job keys
- สคริปต์ continuity exit 0 โดยไม่เร่ง clock และใช้ project soc-accept06 ฐาน/พอร์ตแยก

ติ๊กข้อ 06 และสองรายการค้างตามผล local จริงแล้ว; regression tests รวมใน CI integration script
GitHub CI ของ working changes นี้ **รอยืนยัน**; ยังไม่ commit/push/deploy
ไม่อ้างว่าข้อ 08/09 หรือข้อ 11–13 เสร็จจากผลนี้

ข้อ 07 ตรวจและเติม filters/generated DTO/cursor/backoff เพิ่มแล้ว ดู [รายงานล่าสุด](step-07-verification.md)
