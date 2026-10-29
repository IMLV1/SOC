# Implementation checklist และ prompt สำหรับเขียนโค้ด

วันที่: 13 ตุลาคม 2026

> **อ่านสถานะปัจจุบันก่อน:** เนื้อหา checklist นี้เริ่มเป็นแผนเมื่อ 13 ต.ค. 2026 และบางคำอธิบายด้านล่างเป็น snapshot เก่า ให้ใช้ช่องสถานะกับรายงานที่ระบุ commit เป็นหลักฐาน อย่าสรุปจาก prompt เก่าหรือข้อความ “ยังไม่มี” ที่อาจล้าสมัย
>
> **ทิศทาง RAG:** ผู้ใช้ยืนยันว่าต้องใช้บริการภายนอก (ระบุ Dify) และให้ repository เรียก API เท่านั้น แต่ source checkout ยังมี RAG pipeline ภายในที่ใช้ pgvector และ provider models อยู่ ข้อความข้อ 13–14 ด้านล่างเป็น acceptance/design เดิมของ pipeline นั้น ยังไม่ยืนยันว่า architecture ตรงกับทิศทางใหม่ ต้องแก้ความไม่ตรงกันก่อนอ้างว่าเชื่อมบริการภายนอกแล้ว

ใช้กับ [Development plan](development-plan.md), [Architecture](architecture.md), [API](api.md), [Database](database.md), [CI/CD](ci-cd.md), [RAG](rag-langchain.md) และ [Learning path](learning-path.md)

## เริ่มตรงไหนก่อน

### Dify lesson tutor — 28 ต.ค. 2026 (ไม่ใช่ AI grading ทั้งระบบ)

- [x] Workflow transport แบบ pinned version, Tutor API/DB/job/lesson UI, secret overlay และ fail-closed citations/hash guards
- [x] เพิ่ม migration 0023; isolated PostgreSQL/full backend 262 tests, mocked browser 34 tests, production frontend build และ Node 16 tests ผ่าน ดู [รายงาน](dify-integration-verification.md)
- [x] Supabase wrapper อัปเดต 0023 และ local API readiness; Tutor policy ยัง disabled ไม่มีคำตอบ/คะแนนปลอม
- [ ] รับรอง published Workflow สองโหมด `tutor`/`grade` ที่ส่ง sources, immutable corpus/chunk hashes, no-match branch และ per-call usage/cost accounting; เพดาน US$0.25/day ถูกยกเลิกตามคำขอ 29 ต.ค. ดู [ผลตรวจ](shared-dify-workflow-verification.md)
- [ ] Live authenticated UI→API→DB→worker→Dify→validated result; Dify grading ข้อเขียน/ทบทวนเคส; quality benchmark และ public deployment acceptance

### Flow/presentation follow-up — 27 ต.ค. 2026

- [x] Owner-scoped level status และทางเริ่มเคสสอบถัดไปหลัง passed 1/3; ทดสอบ PostgreSQL รวม 247 tests และ UI progression
- [x] Retry ข้อเขียนคงคำตอบระดับเดิม, ล็อก practice ระหว่าง save/submit; browser regression รวม 31 tests ผ่าน
- [x] อัปเดต Flow/ER/use cases และคู่มือนำเสนอ พร้อมแยกสิ่งที่ยังไม่พร้อม ดู [รายงานรอบนี้](presentation-readiness.md)
- ไม่ใช้ผลนี้ติ๊ก Dify, public deployment, GitHub CI ล่าสุด หรือการส่งคลิป

งานย้าย runtime JSON เป็น DB วันที่ 22 ต.ค. 2026 อยู่ใน
[Database training](database-training.md); ไม่ใช้ผลนี้ติ๊กข้อ AI/RAG หรือ production ทั้งแผน

### Supabase follow-up — 22 ต.ค. 2026 (ไม่เปลี่ยนสถานะทุก phase)

- [x] Fresh Supabase roles/schema/migration wrapper 0001–0021/seed และ API/worker/evaluator readiness
- [x] Same-origin frontend proxy ใช้ cloud DB จริง; Auth bridge/CSRF/pending/encrypted sessions มี regression tests
- [ ] Successful signup/confirmation/login → training run ด้วยบัญชีอีเมลจริงบน Supabase
- [ ] เปิดและตรวจ Google OAuth จริงด้วย project credentials และ exact redirects
- [ ] Existing-account migration, staging/production/restore และ Dify acceptance

หลักฐาน/ข้อจำกัด: [Supabase verification](supabase-verification.md); ไม่ใช้ fake provider ยืนยัน cloud login

เริ่ม **ข้อ 01: ตรวจ contract และวางโครงโปรเจกต์** แล้วทำข้อ 02–07 ให้ login → เริ่ม training run → เห็น event จาก PostgreSQL ผ่าน UI ได้ก่อน จากนั้นเพิ่ม detection/ticket, AI, evaluation, RAG, learning/exam และ deployment ตามลำดับ

ประวัติตอนเริ่ม checklist: branch `f1` มี frontend/backend เพียง .gitkeep; ปัจจุบันระบบมี implementation มากกว่าช่วงเริ่มโครงการ ให้ตรวจสถานะรายข้อตามหลักฐานด้านล่าง `prototype/` ยังคงเป็น reference แยกจากเว็บแอป

ข้อสอบต้องออกแบบ boundary ตั้งแต่ข้อ 01 และทดสอบ gate ตั้งแต่ข้อ 05 แม้จะทำหน้าข้อสอบในช่วงท้าย เพื่อไม่ต้องย้อนแก้ API ที่เผย AI hints/เฉลยในโหมดสอบ

## วิธีใช้ prompt

ส่งทีละข้อ หลังผ่านเกณฑ์จึงไปข้อต่อไป แต่ละข้ออาจต้องหลายรอบแก้ไข ถ้างานใหญ่ให้แบ่งย่อยภายในข้อนั้นโดยคง acceptance criteria อย่าสั่ง “ทำทุก docs ให้เสร็จในครั้งเดียว” เพราะตรวจความถูกต้องและหาสาเหตุที่เสียได้ยาก

แนบข้อความต่อไปนี้ก่อน prompt ของข้อที่เลือก หรืออ้างให้ทำตามกติกานี้:

```text
ทำงานใน repository SOC ตาม docs/implementation-checklist.md เฉพาะข้อที่ฉันระบุ
อ่าน AGENTS.md ถ้ามี และตรวจ branch/status/โค้ดล่าสุดก่อนแก้ อย่าเปลี่ยน branch หรือทับงานที่มีอยู่โดยไม่จำเป็น
ใช้ Next.js App Router + TypeScript, FastAPI + Python, PostgreSQL, SQLAlchemy/asyncpg และ Alembic ตาม docs
เก็บ prototype/ เป็น reference ไม่ย้ายทับ ไม่ใช้ localStorage เป็นข้อมูลจริงหรือย้ายเฉลยไป frontend
ทำ implementation พร้อม migration/API/UI ที่อยู่ในขอบเขต และ tests ที่ตรวจพฤติกรรมสำคัญให้ครบ
หาก docs ขัดกัน ให้บอกจุดขัดและเสนอข้อสรุป; ถ้ากระทบสิทธิ์/คะแนน/ขอบเขตผลิตภัณฑ์ให้ถามก่อนเลือกเอง
อัปเดต checklist เฉพาะสิ่งที่ทดสอบผ่านจริง สรุปไฟล์ที่แก้ วิธีเปิดทดสอบ ผลตรวจ และส่วนที่ยังไม่พร้อม
ยังไม่ publish/deploy ภายนอกหรือเปิดใช้ provider ที่มีค่าใช้จ่าย เว้นแต่ข้อที่สั่งระบุการเชื่อมต่อและ environment ชัดเจน
```

## Checklist ตามลำดับ

### 01 — ยืนยัน contract และ scaffold

- [x] เสร็จและตรวจรับแล้ว — เกี่ยวข้อง SOC-001/002; ผ่านเฉพาะขอบเขตข้อ 01 วันที่ 13 ต.ค. 2026 ดู [ผลตรวจ](step-01-verification.md)

```text
เริ่มข้อ 01: อ่าน docs ทั้งหมด รวม learning-path.md และ rag-langchain.md
สรุปช่องว่างของ contract และสร้าง docs/srs.md, docs/openapi.yaml ฉบับเริ่มต้น พร้อม requirement-to-endpoint mapping
กำหนด training/exam boundary, attempt/run lifecycle, finish/submit, AI hint restrictions และลำดับ lock ให้ตรงกัน
ระบุสิ่งที่ยังต้องตัดสินใจ เช่น rubric, การ override/revoke unlock และ provider โดยไม่แต่งข้อสรุปแทนผู้ใช้
สร้าง scaffold frontend/ เป็น Next.js และ backend/ เป็น FastAPI พร้อม Python worker entrypoint
pin runtime/package versions ที่ตรวจสอบแล้ว สร้าง lockfiles, .env.example และคู่มือเริ่มงาน
เพิ่มหน้าเริ่มต้นและ health endpoint โดยยังไม่สร้าง feature ทั้งระบบ
```

**ผ่านเมื่อ:** frontend/API เริ่มได้, OpenAPI validate ได้, schema ที่ยัง draft ระบุชัด และไม่มี default secret/เฉลยใน bundle การ serialize exam ต้องถูกกำหนดก่อนใช้ endpoints จริง ตัว framework-generated OpenAPI ต้องตรวจเทียบ approved contract เมื่อเพิ่ม route

### 02 — ฐานข้อมูลพื้นฐานและ local environment

- [x] เสร็จและตรวจรับแล้ว — หลัง 01; SOC-001/002; ผ่านขอบเขตข้อ 02 วันที่ 13 ต.ค. 2026

ผลตรวจ 13 ต.ค. 2026: native PostgreSQL 17.11 และ Compose build/up จาก volume ใหม่ผ่าน
container integration 16 tests, frontend smoke 3 tests, roles/provisioning และ down/up persistence ผ่าน
ดู [หลักฐานและขอบเขต](step-02-verification.md)

```text
ทำข้อ 02: สร้าง Compose สำหรับ local development, PostgreSQL, API/worker และ Next.js
ตั้ง SQLAlchemy async sessions, Alembic, migration ledger/lock และ DB roles ตาม database.md
สร้างเฉพาะ schema พื้นฐาน users/sessions/challenges/quotas/assignments/audit ที่จำเป็นสำหรับ auth
เพิ่ม migration และ seed/provisioning command แบบทำซ้ำได้ ไม่ฝังรหัสผ่าน Instructor
เตรียมฐานทดสอบแยก และทดสอบ migrate จากฐานเปล่ารวม role grants
```

**ผ่านเมื่อ:** เครื่องใหม่เปิดระบบและ migrate ได้, restart แล้วข้อมูลอยู่, runtime ไม่ใช้ owner/superuser; ยังไม่จำเป็นต้องสร้างทุกตารางล่วงหน้า ให้เพิ่มตาม feature

### 03 — CI ตั้งแต่เริ่ม

- [x] ผ่าน local และ GitHub CI — หลัง 02; SOC-002; **branch protection ติดข้อจำกัดแพ็กเกจ**

ผลตรวจ 13 ต.ค. 2026: prototype 18, backend foundation 13, container integration 16,
frontend smoke 3 และ gate regression 4 tests ผ่าน; lint/typecheck/build/actionlint ผ่าน
GitHub jobs รวม ci-gate ผ่านแล้ว; failure/cancelled ไม่เป็น success แต่ยังตั้ง branch protection ไม่ได้ (API 403)
ดู [ผลตรวจ](step-03-verification.md) และ [คู่มือ](ci-local.md)

```text
ทำข้อ 03: สร้าง GitHub Actions CI ตาม ci-cd.md สำหรับ prototype, Next.js และ FastAPI
ตรวจ lint/typecheck/unit/build/OpenAPI และ integration กับ PostgreSQL ที่ล้างทิ้งได้
ใช้ lockfiles และ runtime versions เดียวกับ local เพิ่ม ci-gate ที่ไม่ผ่านเมื่อ required job fail/cancel
ยังไม่เพิ่ม deploy job ที่อ้าง credentials หรือ scripts ที่ไม่มีจริง
เพิ่มคู่มือตั้ง required checks และทดสอบคำสั่ง CI ใน local เท่าที่ทำได้
```

**ผ่านเมื่อ:** local checks ผ่าน, workflow/config ตรวจได้; ระบุ “รอยืนยันบน GitHub” หากยังไม่รันจริง ไม่ติ๊กว่าตั้ง branch protection แล้วจากการเขียน YAML อย่างเดียว เพิ่ม regression tests ของ feature ใหม่ใน CI ต่อเนื่องทุกข้อ

### 04 — Authentication, authorization และ Guest demo

- [x] ผ่าน local และ GitHub authentication/Guest acceptance — หลัง 03; SOC-003/004; 14 ต.ค. 2026

ดู [ผลตรวจ](step-04-verification.md): PostgreSQL integration 26, foundation/contract 13,
HTTP smoke 3 และ Chromium E2E 2 ผ่าน; [GitHub CI](https://github.com/IMLV1/SOC/actions/runs/38482432510) ผ่านทั้ง 5 jobs บน `ea59c0e` ใน PR #6

```text
ทำข้อ 04: implement register/login/logout/session/CSRF/me และ role/assignment checks ตาม api.md
ใช้ password hash, opaque cookie session, disabled/revoked checks และ safe response models
ทำหน้า Next.js login/register, session-aware layout และ Guest read-only demo ด้วยข้อมูลตัวอย่างแยก
เชื่อม API จริง ทดสอบ ownership, CSRF, session expiry และการกัน Instructor นอก assignment
```

**ผ่านเมื่อ:** login/logout ใช้งานผ่าน UI จริง, register ไม่ auto-login, Guest เขียนไม่ได้, ผู้ใช้ A อ่านข้อมูล B ไม่ได้ และ cookie/CSRF ใช้ผ่าน local proxy ได้

### 05 — Scenario fixtures และขอบเขต training/exam

- [x] ผ่าน local fixtures/catalog/boundary acceptance — หลัง 04; SOC-005, พื้นฐาน LEARN; 14 ต.ค. 2026

ดู [ผลตรวจ](step-05-verification.md) และ [คู่มือ](scenario-development.md): backend 50 tests ไม่ซ้ำ,
HTTP smoke 3, browser 4 และ bundle leakage 1 ผ่าน; เพิ่ม tests ใน CI แล้ว **รอยืนยันบน GitHub**
ข้อความนี้อธิบายขอบเขตข้อ 05 ตอนนั้นเท่านั้น; run และ exam implementation ถูกเพิ่มในขั้นถัดมา

```text
ทำข้อ 05: เพิ่ม versioned scenario catalog, server-only event fixtures และ private ground truth
เริ่ม S02 สำหรับ training พร้อม normal traffic ก่อน แล้วเตรียม S01–S05 ให้ schema เดียวกัน
แยก demo/training fixtures ออกจาก exam bank ไม่ให้ public catalog สร้าง exam run ได้
วาง exam serializer policy แบบ default-deny สำหรับ AI hints, rubric, label และ initial severity
ข้อกำหนดเดิม: ห้ามเปิด exam ก่อน lesson/level gate พร้อม. ปัจจุบันมี exam implementation เพิ่มแล้ว ให้ดูข้อ 15–17 เพื่อเช็กสถานะและ acceptance ล่าสุด
```

**ผ่านเมื่อ:** seed ซ้ำไม่ duplicate, detector role อ่าน truth ไม่ได้, catalog/bundle ไม่มี fixture อนาคต และ training endpoint ไม่ bypass future exam gate

### 06 — Durable jobs และ simulation runner

- [x] ผ่าน local acceptance — หลัง 05; SOC-006; runner continuity, concurrent pause/release และ lease fencing ผ่านจริง 14 ต.ค. 2026; GitHub ของ changes นี้รอยืนยัน ดู [ผลตรวจ](step-06-10-verification.md)

เกณฑ์ย่อย runner continuity ผ่านจริง 14 ต.ค.: API เริ่ม S02, logout และปิด Chromium แล้ว
events ยังเพิ่ม; restart worker จนครบ 15 events/15 unique keys และ 37 jobs/37 unique dedupe keys
ดู script [runner-continuity.cjs](../frontend/tests/runner-continuity.cjs) และหลักฐานในรายงาน

- [x] API เริ่ม S02 แล้ว PostgreSQL มี released events
- [x] Logout และปิด browser ไม่หยุด runner
- [x] Restart worker แล้ว event/job ไม่ซ้ำ (15 unique events, 37 unique job dedupe keys)
- [x] Concurrent pause/release race ผ่านจริง ทั้ง pause-first และ release-first บน PostgreSQL
- [x] ลำดับ run ก่อน job/resource; recovery/claim transaction แยก; expired/reclaimed lease และ stale analysis output ถูกปฏิเสธ พร้อม rollback เมื่อ lease หมดกลาง transaction

```text
ทำข้อ 06: เพิ่ม runs/instances/versions/events/jobs/idempotency และ Python worker
implement POST runs, pause/resume และ server clock ที่ปล่อยเฉพาะ due events
ทำ quota transaction, one-running-run constraint, lease/heartbeat/fencing และ bounded retries
เตรียม finish cutoff/completion job interface แต่ไม่สร้างคะแนนสำเร็จปลอมก่อน evaluator พร้อม
ทดสอบ concurrent start, pause/release race และ crash ก่อน/หลัง commit แล้ว restart
```

**ผ่านเมื่อ:** API เริ่ม S02 แล้ว PostgreSQL มี released events; logout/ปิด browser ไม่หยุด runner; restart ไม่ทำ event/job ซ้ำ

### 07 — Vertical slice UI: Run → Event explorer

- [x] ผ่าน local acceptance — หลัง 06; SOC-007/008; generated DTO/filters/cursor/backoff และ Chromium E2E ผ่านจริง 14 ต.ค. 2026 ดู [ผลตรวจข้อ 07](step-07-verification.md); GitHub ของ changes นี้รอยืนยัน

Local CI: PostgreSQL 45, HTTP smoke 3, Chromium 9; lint/typecheck/build/contract และ bundle guard ผ่าน

```text
ทำข้อ 07: เชื่อม Next.js กับ run list/start/pause/resume และ Event explorer ผ่าน typed API client
เพิ่ม polling/backoff, filters, cursor/after_seq และรายละเอียด request/response/log ที่ escaped
แสดง loading/empty/error/session expired และรักษา UI state เมื่อ refresh ตาม api.md
ทำ E2E login → start training S02 → อ่าน event → pause/resume พร้อมหน้าจอ 375/768/1440
```

**ผ่านเมื่อ:** เดิน flow นี้ด้วยข้อมูลจริงได้ทั้ง UI/API เป็น milestone แรกก่อนเพิ่ม AI; controls ที่ยังไม่พร้อมต้องบอกตรงจริง

### 08 — Detection, anomaly และ correlation

- [x] ผ่าน local acceptance — หลัง 07; SOC-009; rules/anomaly/correlation v2, S01–S05/normal traffic, duplicate jobs, cross-run evidence และหน้า alert ตรวจด้วย PostgreSQL/Chromium 14 ต.ค. 2026 ดู [ผลตรวจ](step-06-10-verification.md); GitHub ของ changes นี้รอยืนยัน

```text
ทำข้อ 08: implement versioned rules/anomaly/correlation, detections/evidence และ alerts
ให้ policy สร้าง automatic ticket แบบ idempotent ตาม database.md และแสดงรายการ alert ผ่าน UI
เพิ่ม fixtures/test cases ครบ S01–S05 และ normal traffic โดย detector ไม่อ่าน scenario label/ground truth
ทดสอบ duplicate jobs, cross-run evidence และ S05 ที่ต้องเข้าทาง anomaly จริง
```

**ผ่านเมื่อ:** มีเหตุผล/หลักฐานอ้างได้, soft-deleted automatic ticket ไม่ถูกสร้างใหม่ด้วย correlation เดิม, ไม่สรุป successful compromise จาก blocked request

### 09 — Ticket/Note CRUD, assessment และประวัติ

- [x] ผ่าน local acceptance — หลัง 08; SOC-010/013; PostgreSQL integration 6 tests, investigation browser E2E, typecheck/lint และ OpenAPI contract checks ผ่าน 14 ต.ค. 2026; disposition คง 3 ค่าไว้ตามข้อสรุปผู้ใช้ ดู [ผลตรวจ](step-06-10-verification.md)

```text
ทำข้อ 09: implement ticket detail/manual create/update/delete/restore, assessment revisions
และ note CRUD/version/evidence พร้อม audit และ expected_version
เชื่อมหน้า investigation จาก prototype กับ API จริง รองรับ 409 โดยไม่ทำ draft หาย
ทดสอบ ownership, cross-run refs, deleted parent, concurrent edit และ run read-only
```

**ผ่านเมื่อ:** ประวัติไม่ถูกเขียนทับ, ผู้เรียนกับ Instructor ใช้สิทธิ์ต่างกัน และ ticket/note mutation ทุกทางถูกล็อกหลัง completing

### 10 — AI pipeline ด้วย mock ที่ทดสอบได้

- [x] mock acceptance ผ่านตามรายงานเดิม; รายงาน real Gemini S02 เป็นหลักฐานย้อนหลังเท่านั้นและไม่ใช่ provider ปัจจุบัน ดู [ผลตรวจ](step-06-10-verification.md)

```text
ทำข้อ 10: สร้าง AnalysisProvider, frozen evidence snapshots, analyses/attempts และ async jobs
เริ่ม mock adapter แบบ deterministic พร้อม Pydantic structured result และ citation/evidence validation
implement GET analysis/retry และ UI statuses โดยแสดง mode=mock ชัดเจน
ทำ quota reservation/reconciliation และ timeout/invalid output/retry tests โดยไม่เรียก provider จริง
```

**ผ่านเมื่อ:** mock ไม่ปนผล benchmark จริง, refs นอก snapshot ถูกปฏิเสธ และ AI ไม่แก้คำตอบของคน

### 11 — Evaluation, completion และ Instructor

- [x] ผ่าน local acceptance — หลัง 10; SOC-014/015 บางส่วน; 15 ต.ค. 2026

ดู [ผลตรวจข้อ 11](step-11-verification.md): PostgreSQL integration 50, Chromium E2E 11,
HTTP smoke 3 และ metrics/experiment/OpenAPI tests ผ่าน; lint/typecheck/mypy ผ่าน
GitHub CI ของ branch นี้ยังรอยืนยัน; C ยัง unavailable และ human scoring เป็น N/A ตาม policy ที่ยังไม่อนุมัติ

```text
ทำข้อ 11: implement finish → completing → completed, pipeline drain และ immutable evaluation snapshot
เพิ่ม deterministic metrics, locked ground truth, JSON export และ Instructor accounts/quotas/comments/review
ตรวจ read-only หลัง finish และไม่ให้ Instructor เขียนทับ assessment/note
ทำ experiment framework A/B/C โดย A/B ใช้ detector จริง และ C unavailable จน provider จริงพร้อม
ทดสอบ cutoff, late AI result, deleted ticket denominator และ N/A metrics
```

**ผ่านเมื่อ:** คะแนนคำนวณจาก snapshot ไม่เปลี่ยนเมื่อมีงานมาช้า, instructor review ตรวจ assignment; ยังไม่อ้างว่าทดลอง C จริงเสร็จในขั้นนี้

### 12 — เชื่อม AI provider จริง

- [ ] Dify integration ยังไม่ผ่าน acceptance; ผล Gemini Free Tier ในรายงานข้อ 12 เป็นหลักฐานย้อนหลัง ไม่ใช่ provider ปัจจุบัน

การเชื่อม Gemini ที่ระบุในรายงานข้อ 10–12 เป็น implementation/ผลทดสอบเดิม; ผู้ใช้เลือก Dify แทนแล้ว และ runtime ปัจจุบันไม่เรียก Gemini. Dify integration ยังไม่ผ่าน acceptance
การทดสอบ rate/usage ของ Gemini เป็นผลย้อนหลัง; ต้องทำ quota/unknown-usage policy ให้ตรงกับ Dify ก่อนเปิดใช้งาน
ดู [ผลตรวจข้อ 12](step-12-verification.md); PostgreSQL 55, backend unit/contract 49,
HTTP smoke 3, Chromium E2E 11 ผ่าน. C จริงเป็น operator CLI; ยังไม่อ้าง production readiness.

```text
ทำข้อ 12: เชื่อม Dify API เป็น external provider รายเดียว โดยเก็บ app key ฝั่ง server
ตอนนี้ยังไม่มี Base URL/app key; คง mock และ fail closed จน contract, budget, citation/revocation และ runtime tests พร้อม
เพิ่ม rate limit, timeout, cost caps, retry/idempotency limitations และ unknown-usage reconciliation
เมื่อมีข้อมูลและสิทธิ์พร้อม ทำ bounded smoke test และ experiment C จริง เก็บผลแยกจาก mock
```

**ผ่านเมื่อ:** มีผล real call ที่ตรวจย้อนกลับได้ภายในงบ, provider ล่มไม่หยุด investigation และไม่มี secrets ใน browser/log

### 13 — Knowledge corpus, pgvector และ ingestion

รายงานวันที่ 15 ต.ค. 2026 ระบุว่า local/mock acceptance ของ storage/ingestion/publish/revoke, roles, retrieval tests และ run pin ผ่านใน implementation ภายในชุดนั้น ดู [ผลตรวจข้อ 13](step-13-verification.md). ข้อความนี้เป็นหลักฐานของโค้ด/commit ตอนนั้น ไม่ใช่การรับรอง architecture ภายนอกตามทิศทางที่ผู้ใช้ยืนยันภายหลัง

- [x] ผ่าน local/mock acceptance — หลัง 10; ต่อจาก 12 ตามลำดับแนะนำ; RAG-001/002

```text
ขั้นตอนเดิมของข้อ 13 ตาม rag-langchain.md: เพิ่ม kb schema/pgvector, approved Markdown manifest,
chunking, embedding profile, ingestion jobs และ publish/revoke knowledge release
ไม่ index docs ทั้งโฟลเดอร์หรือ private answer key ใช้ fake embeddings ใน CI
สร้าง golden/held-out retrieval tests และ pin release ต่อ run พร้อม dimension/model migration strategy
provider embeddings จริงต้องผ่านการเลือกและงบเช่นเดียวกับข้อ 12
```

**ผ่านเมื่อ:** ingest ซ้ำไม่ duplicate, partial corpus ไม่ถูก publish, retriever role อ่านเฉลยไม่ได้ และ revoke ตัดการใช้งานได้

### 14 — RAG และ Ask AI (แบบเดิมใน repository)

> Acceptance ด้านล่างเขียนสำหรับ pipeline RAG ภายในเดิม ไม่ใช่ข้อกำหนดการเชื่อม Dify API; ต้องปรับ contract, checklist และหลักฐานให้ตรงบริการภายนอกก่อนปิดข้อ 14

- [ ] ตรวจรับ Step 14 ทั้งข้อ — implementation และ GitHub CI ล่าสุดผ่านแล้ว แต่ independent review, paired answer benchmark ของ release v2 และ provider usage reconciliation ยังไม่ผ่าน ดู [ผลตรวจข้อ 14](step-14-verification.md)
- [x] Local API/UI, frozen citations/retry, revocation และ race/security regressions ผ่าน; CI ใช้ fake embeddings
- [x] Real Free Tier smoke และ RAG/no-RAG pilot 50 คำถาม วัดแยกไทย/อังกฤษ เก็บ failures/call IDs/usage ตามจริง
- [x] เพิ่ม model tokenizer preflight, shared dispatch cap, telemetry และ calibration release ใหม่; real smoke ผ่าน
- [x] วัด retrieval v2 บน 50 คำถามใหม่แยก validation: TH Recall@5=0.95 / EN=1.00 ตาม developer labels; เก็บ baseline TH=0.80 ตามจริง
- [x] ทำ agent self-review: relevance 100 คำถาม/claims 57 รายการ พร้อมเหตุผลและ unsupported cases; ไม่ใช่ human acceptance ดู [รายงาน self-review](step-14-agent-review.md)
- [ ] ผู้ตรวจอิสระยืนยัน relevance/grounding (supported claims ≥90%) และ paired answer benchmark ของ release v2; review packets พร้อม แต่ผู้เขียน implementation/agent ห้ามลงคะแนนแทนผู้ตรวจ และยังไม่ dispatch provider เพิ่ม ดู [คู่มือผู้ตรวจ](step-14-review-guide.md)
- [ ] Reconcile unknown usage 6 calls ด้วยข้อมูล provider ที่ยืนยันได้; AI Studio project ไม่มีข้อมูลที่ใช้จับคู่ และ Google Cloud Console ยังอยู่หน้า Terms of Service จึงไม่มีหลักฐาน 0 tokens หรือ usage report
- [x] GitHub CI ผ่านบน GitHub สำหรับ `a4ea423` และ `b72a549` (run 38875091514, 38877535995) และ main หลัง merge PR #15 ที่ SHA `3ebe256` (run 39395631902); ไม่ใช่หลักฐาน human quality review หรือ deployment

```text
ทำข้อ 14: implement authorized retrieval → LangChain structured generation → citation validation
เชื่อม triage และ ticket questions API/UI พร้อม frozen citations, budgets และ source drawer
รองรับ no_match/unavailable/withdrawn, retry snapshot เดิม และห้าม Ask AI ใน exam ก่อน submit
ทดสอบ cross-run citation, prompt injection, revocation ทุก projection และ finish/question race
ทำ benchmark no-RAG เทียบ RAG ตาม held-out set พร้อมแยกไทย/อังกฤษและต้นทุน
```

**ผ่านเมื่อ:** citation มีจริงและอยู่ใน context, ไม่อ้างว่าคู่มือเป็นหลักฐานของเหตุการณ์; รายงานคุณภาพ/ข้อจำกัดจริง ไม่ใช้ mock เป็นหลักฐานความแม่นยำ

### 15 — Learning path, onboarding และ server-side progress

เพิ่มเติม 21 ต.ค. 2026: มี training JSON 3 ระดับ / 9 บท / 45 ขั้น และหน้า `/demo/learning`
แบบไม่เรียกฐานข้อมูล สำหรับตรวจเนื้อหาก่อนเชื่อม environment จริงเท่านั้น
ไม่เปลี่ยนผลสอบ/progress/unlock และไม่ใช่ acceptance ของ multi-level server gates หรือ Dify
ดู [คู่มือ](learning-content-seed.md) และ [ผลตรวจ preview](learning-preview-verification.md)

- [x] ผ่าน local acceptance — หลัง 04/05; lesson persistence/owner/gate integration และ `/learning` browser refresh/responsive flow ผ่าน 18 ต.ค. 2026; ดู [ผลตรวจข้อ 15](step-15-verification.md)

สถานะปัจจุบัน: local acceptance ผ่าน; disposable Compose ล่าสุด 77 integration passed/82 deselected, smoke 3 passed, browser E2E 26 passed/1 skipped รวม journey retake; GitHub CI run 39495958300 ผ่านครบทุก job บน `c4abb42`. ดู [ผลตรวจข้อ 15](step-15-verification.md)

```text
ทำข้อ 15 ตาม learning-path.md: implement learning levels/lessons/progress และ onboarding ใน Next.js
พาอ่าน Method/Path/Response/account/IP/timeline ทีละขั้น เก็บ progress ตาม lesson version ฝั่ง server
เพิ่ม learning path APIs และ prerequisite policy เพื่อเปิดข้อสอบ โดย client ส่ง passed/unlocked เองไม่ได้
Guest อ่าน demo ได้ ทบทวนบทเรียนได้ และ refresh แล้วเรียนต่อได้
```

**หมายเหตุการตัดสินใจ:** ผู้ใช้ยืนยัน 17 ต.ค. 2026 ว่าต้อง login ก่อนอ่านเนื้อหาบทเรียน จึงให้ Guest ดูเฉพาะ metadata/demo ตาม [ผลตรวจข้อ 15](step-15-verification.md); รายละเอียดเกณฑ์รับงานยังรอ checks ที่ระบุในรายงาน

**ผ่านเมื่อ:** ผู้เรียนใหม่เริ่มต้นถูกระดับ, จบบทเรียนไม่เท่ากับผ่านข้อสอบ, แก้ localStorage/เรียก API ตรงแล้ว bypass gate ไม่ได้

### 16 — Blind exam, immutable submission และ retake

- [x] ผ่าน local acceptance และ GitHub CI — หลัง 06/09/11/15; LEARN exam; GitHub run 39411788826 ผ่านทุก job บน `75ae111`; ดู [ผลตรวจข้อ 16](step-16-verification.md)

สถานะปัจจุบัน: migration/seed, server-selected attempt, blind DTO, atomic submit/replay และ browser flow เริ่มข้อสอบ/ส่งคำตอบ/needs_review ผ่าน. Retake policy: 3 ครั้งต่อ case/24 ชม. (สูงสุด 9 ต่อ level เมื่อมี 3 cases), cooldown หลังตก 1 ชม.; PostgreSQL integration ยืนยัน case rotation/cap, concurrent starts ได้ active attempt เดียว และ latest-result จำกัดตามเจ้าของ. Disposable Compose ล่าสุด 21 ต.ค. 2026 บน branch `codex/retake-browser-acceptance` ผ่าน: integration 77 passed/82 deselected, smoke 3, browser 26 passed/1 skipped; browser journey Instructor review/feedback และเริ่ม retake ใหม่หลัง cooldown หมดผ่าน. GitHub CI run 39494965944 ผ่านครบทุก job บน `5bfcdb2`. ดู [ผลตรวจข้อ 16](step-16-verification.md)

```text
ทำข้อ 16: implement exam bank, server-selected attempts, one-active-exam/quota checks และ blind serializers
ทำหน้า exam กับ submit คำตอบ/evidence/severity/disposition/reason แบบ atomic และ idempotent
ปิดช่อง hint/ground-truth ผ่าน run/alerts/tickets/analysis/questions/export ทุกทางก่อนเวลาที่ policy อนุญาต
แยก finish ของ training จาก submit ของ exam ไม่ให้ generic finish bypass grading
เพิ่ม retake เป็น attempt ใหม่ตาม policy; grading ที่ยังไม่พร้อมต้อง pending/needs_review ไม่ผ่านเอง
```

**ผ่านเมื่อ:** หลักฐานไม่ครบส่งไม่ได้, submit สองแท็บได้คำตอบเดียว, answer key ไม่อยู่ใน response/bundle และ demo ไม่เผยข้อสอบชุดเดียวกัน

### 17 — Grading, feedback, review และปลดล็อกระดับ

- [ ] เสร็จและตรวจรับแล้ว — หลัง 12/14/16; LEARN grading

สถานะ: frozen submission, deterministic rubric, assignment-scoped review/audit, concurrent review, unlock ครบทุก case และ override history/non-revocation ผ่าน PostgreSQL integration; browser journey Instructor review → learner feedback ผ่าน API/PostgreSQL จริงแล้วใน disposable Compose. GitHub CI run 39495958300 ผ่านครบทุก job บน `c4abb42`; ยังขาด coverage interleavings เพิ่มเติม และข้อ 17 ขึ้นกับตรวจรับข้อ 14 ตามลำดับ ส่วน AI grading จริงยังไม่เปิด จึงยังไม่ติ๊ก ดู [ผลตรวจข้อ 17](step-17-verification.md)

```text
ทำข้อ 17: implement versioned rubric, deterministic checks และ AI/RAG grading หลัง frozen submission
ใช้ grading role แยก private key จาก learner/detector/triage; ไม่ส่งเฉลยเข้า shared knowledge corpus
เก็บ grading revisions/citations/model/knowledge versions; ambiguity/outage/invalid citation เป็น needs_review
เพิ่ม Instructor review/override พร้อมเหตุผล/audit และ atomic level unlock ตาม policy ที่ตกลงไว้
ยึด policy D-01–D-04 ใน SRS §8; เปลี่ยน policy ต้องเพิ่ม version/review decision ก่อนใช้กับ attempt ใหม่
```

**ผ่านเมื่อ:** AI ไม่ปลดล็อกเอง, ผ่านทุกเคสจึงเลื่อนระดับ, override ไม่ลบประวัติ, retake ไม่เขียนทับ attempt เดิม และมี tests submit/grade/unlock races

### 18 — Staging deployment และ operational checks

- [ ] เสร็จและตรวจรับแล้ว — หลัง 17 และ quality gates; SOC-016

สถานะ: Docker Engine พร้อมและ local CI Compose ล่าสุดผ่าน (77 integration passed/82 deselected, smoke 3, browser 26/1 skip); ยังไม่มี staging/registry/hosting ที่เลือก จึงยังไม่มี deploy, rollback หรือ backup/restore evidence; ดู [ผลตรวจข้อ 18](step-18-verification.md)

```text
ทำข้อ 18: เตรียม production Docker images ของ Next.js และ FastAPI/Python worker,
release manifest/image digests, deploy/migrate/smoke/rollback scripts และ staging workflow ตาม ci-cd.md
ตรวจ hosting/registry/domain/credentials ที่มีจริงก่อนต่อ provider adapter; ขอข้อมูลที่ขาดโดยไม่สมมติว่า deploy สำเร็จ
เมื่อ environment และการ deploy staging ได้รับอนุญาตแล้ว ให้ deploy staging และตรวจ HTTPS/cookie/CSRF,
worker heartbeat, queue failures, migrations, pgvector และ critical flows พร้อม backup/restore drill
```

**ผ่านเมื่อ:** staging ใช้ DB/credentials แยก, deploy commit ที่ CI ผ่านจริง, backup restore ได้พร้อมผลวัด; setup บน GitHub/hosting ที่ยังไม่ได้ทำให้ระบุ pending

### 19 — Acceptance, production และส่งมอบ

- [ ] เสร็จและตรวจรับแล้ว — หลัง 18; SOC-017

สถานะ ณ 21 ต.ค. 2026: local Compose ยืนยัน lesson → exam/submit → Instructor review/feedback → รอ cooldown → เริ่ม retake ใหม่; PostgreSQL test ครอบคลุม concurrent retake start หลัง attempt ก่อนหน้าตกและ cooldown หมด. GitHub CI run 39495958300 ผ่านครบทุก job บน `c4abb42`; ยังขาด export/accessibility/load audit และ staging/production evidence; ดู [ผลตรวจข้อ 19](step-19-verification.md)

```text
ทำข้อ 19: ตรวจ requirement coverage ของ docs ทั้งหมดกับ implementation และเติมช่องว่างที่อยู่ใน scope
รัน E2E Guest → register/login → lessons → exam → submit → feedback/review → retake/unlock
รวม training/investigation/RAG/export และ failure paths ตรวจ responsive/accessibility/load ตามเป้าหมาย
ทดสอบ migration failure, application rollback และ restore; ทำคู่มือ operator/ผู้เรียนและบันทึกข้อจำกัด
เตรียม production release จาก digests เดียวกับ staging พร้อมหลักฐานตรวจรับ
deploy production เฉพาะเมื่อ environment พร้อมและได้รับการอนุมัติตาม release policy แล้ว
```

**ผ่านเมื่อ:** checklist requirement ครบหรือระบุข้อยกเว้นที่ตกลงแล้ว, critical tests ผ่านจริง, มีผลวัด/URL/คู่มือ และไม่รายงาน benchmark/production deployment ที่ไม่ได้เกิดขึ้น

## จุดตัดสินใจที่ควรเตรียม

| ก่อนข้อ | ข้อมูลที่ต้องตกลง |
|---|---|
| 01/16/17 | exam lifecycle, rubric/version, pass criteria, incomplete submission, retake/quota และผลของ Instructor override ต่อ unlock |
| 12 | chat provider/model, credentials ผ่าน secret store, งบ smoke/benchmark และ privacy policy |
| 13/14 | embedding provider/model/dimension, approved corpus, reviewer และงบ ingestion |
| 18 | hosting รองรับ worker/pgvector, GitHub plan, registry, domains, environment access และงบ |
| 19 | production release policy, ผู้อนุมัติ/ผู้ดูแล และ retention/backup ที่ใช้งานจริง |

ข้อมูลเหล่านี้ไม่ได้ขวางการเริ่ม scaffold/auth/runner ด้วย mock แต่ต้องไม่อ้างว่า real integration หรือการสอบจริงพร้อมก่อนตัดสินใจครบ

## บันทึกผลหลังแต่ละข้อ

ใช้ตารางนี้เพิ่มแถวเมื่อทำจริง; ช่อง checkbox ด้านบนหมายถึงผ่าน acceptance ไม่ใช่เพียงเริ่มเขียนโค้ด

| ข้อ | สถานะ (ยังไม่เริ่ม/กำลังทำ/รอตรวจ/ผ่าน) | หลักฐาน tests/ไฟล์/commit | สิ่งที่ค้าง |
|---|---|---|---|
| 01 | ผ่าน — contract draft + scaffold | [SRS](srs.md), [OpenAPI](openapi.yaml), [คู่มือ](getting-started.md), [ผลตรวจ](step-01-verification.md); backend 13 tests, frontend 3 smoke tests, lint/typecheck/build/OpenAPI และ local startup ผ่าน | Domain schemas ยัง draft; rubric/retake/override-unlock/provider pending; DB/CI/features อยู่ข้อถัดไป ยังไม่ deploy |
| 02 | ผ่าน — local DB foundation | [คู่มือ](local-development.md), [ผลตรวจ](step-02-verification.md); native backend 29 tests, container integration 16, Compose build/up, frontend smoke 3, provisioning ซ้ำ, outage recovery และ named-volume down/up persistence ผ่าน | ยังไม่เริ่ม auth/CI/jobs หรือ production deployment |
| 03 | ผ่าน local และ GitHub CI | [workflow](../.github/workflows/ci.yml), [คู่มือ](ci-local.md), [ผลตรวจ](step-03-verification.md); ทุก job ผ่านบน GitHub และ failure/cancelled ไม่เป็น success | Branch protection/rulesets API 403 เพราะ private repository plan; ยังไม่ยืนยัน enforced merge blocking; ไม่ deploy |
| 04 | ผ่าน local และ GitHub auth/Guest acceptance ตามรายงาน | [คู่มือ](auth-development.md), [ผลตรวจ](step-04-verification.md); integration 26, foundation/contract 13, HTTP smoke 3, Chromium E2E 2 และทั้ง 5 GitHub jobs ผ่าน | รายงานนี้บันทึกช่วงก่อนมี runner/ข้อสอบ; ดู checklist และรายงานใหม่ก่อนอ้างสถานะปัจจุบัน |
| 05 | ผ่าน local fixtures/catalog/boundary ตามรายงาน | [คู่มือ](scenario-development.md), [ผลตรวจ](step-05-verification.md); migration/seed/grants/selector, backend 50 ไม่ซ้ำ, HTTP 3, browser 4, bundle 1 และ static/build ผ่าน | รายงานนี้เป็น snapshot ก่อนพัฒนาขั้นถัดไป ไม่ใช่สถานะล่าสุดของ runner/exam |
| 16 | ผ่าน local acceptance และ GitHub CI บน SHA ที่บันทึก | [ผลตรวจ](step-16-verification.md); 21 ต.ค. disposable Compose: PostgreSQL integration 77 passed/82 deselected, smoke 3, browser 26 passed/1 skipped; browser เริ่ม retake หลัง cooldown ผ่าน; GitHub CI run 39494965944 ผ่านบน `5bfcdb2` | staging acceptance ยังรอยืนยัน |
| 19 | กำลังตรวจรับ | [ผลตรวจ](step-19-verification.md); local Compose ตรวจ feedback/review, cooldown และ retake start; frontend lint/typecheck, Ruff check/format และ diff check ผ่าน; GitHub CI run 39494965944 ผ่านบน `5bfcdb2` | ยังขาด export/accessibility/load coverage และ staging/rollback/restore |

ถ้าข้อหนึ่งยังไม่ผ่าน ให้ใช้ prompt ต่อว่า: “แก้ข้อ NN ต่อจากผลทดสอบล่าสุดให้ผ่าน acceptance ที่ยังค้าง โดยไม่เริ่มข้อถัดไปและไม่เปลี่ยน test ให้ยอมรับพฤติกรรมผิด”
