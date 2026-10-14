# ผลตรวจข้อ 06–10 (14 ตุลาคม 2026)

กิ่ง `codex/steps-06-10` เริ่มจาก `origin/main` ล่าสุด ณ วันที่ทำงานนี้ ไม่แตะ `prototype/` และไม่ deploy/push ภายนอก การทดสอบฐานข้อมูลใช้ `test-db` แบบ tmpfs; การทดสอบ UI ใช้ Compose project แยก `soc-verify-steps` บน loopback 4300/8400/55433 ไม่ใช้ฐานข้อมูลของ project เดิม

## ผ่านและตรวจรับแล้ว

- **06:** Alembic 0004 สร้าง runs/instances/versions/events/jobs/idempotency; worker ใช้ PostgreSQL clock, lease, fencing, retry สูงสุด 3 ครั้ง และ recovery ของ run ที่ไม่มี wake-up. Integration ทดสอบ start พร้อมกัน, idempotency/quota, crash ก่อน/หลัง domain commit, pause/resume และ resume ที่ยังไม่มี event ใหม่. Browser login แล้วเริ่ม S02 จริง, logout และ restart worker: run เดิมจบ schedule เป็น `reviewing`, มี 15/15 released events และ release_seq ซ้ำ 0. `finish` คงสถานะ `completing` พร้อม cutoff/job; ยังไม่มีผลคะแนน เพราะ evaluator เป็นข้อ 11.
- **07:** Next.js run list/start และ Event explorer ใช้ API จริง มี polling/backoff, source filter, after_seq/cursor และ request/response/log แสดงเป็น escaped text. HTTP regression ตรวจ cursor/filter/time range; browser เดิน login → start S02 → อ่าน event → pause → refresh → resume และตรวจ viewport 375/768/1440 ว่าไม่มี horizontal overflow. ไฟล์ Playwright E2E อยู่ใน `frontend/tests/browser/runs.spec.ts` แต่รอบนี้ยังไม่ได้รันด้วย Playwright CLI; หลักฐาน E2E ที่ผ่านเป็นการทดสอบ browser แบบลงมือจริง.
- **08:** Alembic 0005 และ worker detector สร้าง versioned rule/anomaly/correlation, evidence, alert และ automatic ticket. Tests ครอบ S01–S05, normal page view, S05 anomaly, blocked request ไม่สรุป compromise สำเร็จ, rerun detector ไม่เพิ่ม detection และ soft-deleted automatic ticket ไม่ถูกสร้างซ้ำ. DB composite FK ปฏิเสธ evidence ข้าม run. Browser S02 เห็น alert/ticket/mock analysis จากข้อมูลที่ปล่อยจริง.
- **09:** Alembic 0006 เพิ่ม Ticket/Note CRUD, assessment revisions, note versions/evidence, audit และ expected_version. HTTP/integration tests ครอบ owner/Instructor assignment และ Instructor PATCH, cross-run refs, deleted parent, 409 concurrent edit, completing read-only รวมทั้ง ticket timeline และ list filters/cursor. Browser จริงสร้าง note/assessment และเปิดสองแท็บให้เกิด 409 โดย draft ที่กรอกไว้ไม่หาย. ประวัติเดิมคงอยู่หลังแก้ไข.
- **10:** Alembic 0007 เพิ่ม `AnalysisProvider` แบบ deterministic mock, frozen evidence, attempts, async job, citation subset validation, reservation/reconciliation, GET/retry และ list filter/cursor. Tests ครอบ timeout, invalid output, retry ผ่าน HTTP/idempotency, snapshot/ref rejection และ quota release; browser ตรวจ invalid_output → retry → succeeded โดยแสดง `mode=mock`. Mock ไม่เขียน assessment ของคนและไม่ใช้เป็นคะแนน/benchmark จริง. ไม่มีการเรียก provider ที่มีค่าใช้จ่าย.

## ยังไม่พร้อมหรือยังไม่ได้ตรวจ

- Playwright CLI E2E ยังไม่ได้รันในเครื่องนี้ (Node host เป็น 23 แต่ frontend pin Node 24 และยังไม่มี browser binary ของ Playwright); ทดสอบ flow ด้วย browser จริงแบบลงมือแทน. ไฟล์ E2E ที่เขียนไว้ยังเป็น automated test ที่รอรันใน environment ที่พร้อม.
- ข้อ 11 evaluation/completion ยังไม่เสร็จ: `finish` สร้าง cutoff/job และล็อก mutation แต่ไม่สร้างคะแนนหรือคำตัดสินสำเร็จปลอม. ยังไม่มี RAG/provider จริงหรือ global paid-token budget เพราะอยู่นอก mock scope และไม่ได้เปิดใช้ภายนอก.
- ยังไม่ได้ deploy, publish, push หรือเปิด paid provider. Compose verification stack เป็น local loopback/ฐานข้อมูลแยกเท่านั้น.

## คำสั่งตรวจซ้ำ

1. `python3 scripts/init-local.py` (สร้าง secrets เฉพาะเมื่อยังไม่มี)
2. `docker compose --profile test up -d test-db`
3. `docker compose --profile test run --rm test` (หลัง build test image ใหม่)
4. `docker compose build frontend` และ `docker run --rm soc-frontend-check:local npm run lint` หลัง build stage image สำหรับ lint
5. `docker run --rm -v "$PWD:/repo:ro" -w /repo/backend -e PYTHONPATH=/repo/backend soc-local-test:latest python -m pytest tests/test_foundation.py -q -p no:cacheprovider`
6. สำหรับเว็บจริงใช้ Compose project/ports แยก เช่น `SOC_DB_PORT=55433 SOC_API_PORT=8400 SOC_WEB_PORT=4300 docker compose -p soc-verify-steps up -d --build` แล้วเปิด `http://127.0.0.1:4300/runs` (อย่าใช้ project/ports นี้พร้อมข้อมูลเดิมโดยไม่ตรวจ).

ผลล่าสุด: backend integration **48 passed**, foundation/contract **13 passed** และ generated API types `--check` ผ่าน; Ruff, Mypy, Next.js production build, frontend lint และ HTTP smoke **3 passed**. มีเพียง warning ของ Starlette/TestClient dependency ที่ไม่ทำให้ test ล้ม. Auth rate-limit test ตรึงเวลาใน test เพื่อไม่ให้ข้าม bucket ระหว่างนาที.

## จุดไม่ตรงกันใน docs และข้อสรุปที่ใช้

`database.md` §migration outline ยังเรียก events/detection ว่า revision `003` แต่ revision `0003_scenario_catalog` ถูกใช้ไปแล้วในข้อ 05. จึงต่อ Alembic เป็น `0004`–`0007` แบบ append-only ไม่แก้ migration เดิม; ควรปรับ outline ให้ตรงกับ migration ที่ใช้งานจริงในรอบเอกสารต่อไป. `api.md` ระบุ list filters/cursor และ timeline กว้างกว่าข้อความย่อใน checklist; รอบนี้ implement และทดสอบส่วนของข้อ 09/10 ที่เกี่ยวข้อง แทนการตัด contract. ไม่มีการเลือกเปลี่ยนสิทธิ์/คะแนน/ขอบเขตผลิตภัณฑ์เอง.
