# Implementation checklist และ prompt สำหรับเขียนโค้ด

วันที่: 13 ตุลาคม 2026

ใช้กับ [Development plan](development-plan.md), [Architecture](architecture.md), [API](api.md), [Database](database.md), [CI/CD](ci-cd.md), [RAG](rag-langchain.md) และ [Learning path](learning-path.md)

## เริ่มตรงไหนก่อน

เริ่ม **ข้อ 01: ตรวจ contract และวางโครงโปรเจกต์** แล้วทำข้อ 02–07 ให้ login → เริ่ม training run → เห็น event จาก PostgreSQL ผ่าน UI ได้ก่อน จากนั้นเพิ่ม detection/ticket, AI, evaluation, RAG, learning/exam และ deployment ตามลำดับ

ตรวจ repository วันที่เขียน checklist: อยู่ branch `f1`, `frontend/` และ `backend/` มีเพียง `.gitkeep`; prototype ใช้งานเป็น reference ได้ แต่ไม่ใช่ production backend ช่องด้านล่างยังไม่ติ๊ก เพราะการมีเอกสารไม่ถือว่า implementation เสร็จ

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

- [x] ผ่าน local authentication/Guest acceptance — หลัง 03; SOC-003/004; 14 ต.ค. 2026

ดู [ผลตรวจ](step-04-verification.md): PostgreSQL integration 26, foundation/contract 13,
HTTP smoke 3 และ Chromium E2E 2 ผ่าน; ยังไม่ push/run GitHub CI สำหรับ branch ข้อ 04

```text
ทำข้อ 04: implement register/login/logout/session/CSRF/me และ role/assignment checks ตาม api.md
ใช้ password hash, opaque cookie session, disabled/revoked checks และ safe response models
ทำหน้า Next.js login/register, session-aware layout และ Guest read-only demo ด้วยข้อมูลตัวอย่างแยก
เชื่อม API จริง ทดสอบ ownership, CSRF, session expiry และการกัน Instructor นอก assignment
```

**ผ่านเมื่อ:** login/logout ใช้งานผ่าน UI จริง, register ไม่ auto-login, Guest เขียนไม่ได้, ผู้ใช้ A อ่านข้อมูล B ไม่ได้ และ cookie/CSRF ใช้ผ่าน local proxy ได้

### 05 — Scenario fixtures และขอบเขต training/exam

- [ ] เสร็จและตรวจรับแล้ว — หลัง 04; SOC-005, พื้นฐาน LEARN

```text
ทำข้อ 05: เพิ่ม versioned scenario catalog, server-only event fixtures และ private ground truth
เริ่ม S02 สำหรับ training พร้อม normal traffic ก่อน แล้วเตรียม S01–S05 ให้ schema เดียวกัน
แยก demo/training fixtures ออกจาก exam bank ไม่ให้ public catalog สร้าง exam run ได้
วาง exam serializer policy แบบ default-deny สำหรับ AI hints, rubric, label และ initial severity
ยังไม่เปิดให้เริ่ม exam จน lesson/level gate พร้อม เพิ่ม tests ว่า assets/API/error ไม่เผยเฉลย
```

**ผ่านเมื่อ:** seed ซ้ำไม่ duplicate, detector role อ่าน truth ไม่ได้, catalog/bundle ไม่มี fixture อนาคต และ training endpoint ไม่ bypass future exam gate

### 06 — Durable jobs และ simulation runner

- [ ] เสร็จและตรวจรับแล้ว — หลัง 05; SOC-006

```text
ทำข้อ 06: เพิ่ม runs/instances/versions/events/jobs/idempotency และ Python worker
implement POST runs, pause/resume และ server clock ที่ปล่อยเฉพาะ due events
ทำ quota transaction, one-running-run constraint, lease/heartbeat/fencing และ bounded retries
เตรียม finish cutoff/completion job interface แต่ไม่สร้างคะแนนสำเร็จปลอมก่อน evaluator พร้อม
ทดสอบ concurrent start, pause/release race และ crash ก่อน/หลัง commit แล้ว restart
```

**ผ่านเมื่อ:** API เริ่ม S02 แล้ว PostgreSQL มี released events; logout/ปิด browser ไม่หยุด runner; restart ไม่ทำ event/job ซ้ำ

### 07 — Vertical slice UI: Run → Event explorer

- [ ] เสร็จและตรวจรับแล้ว — หลัง 06; SOC-007/008

```text
ทำข้อ 07: เชื่อม Next.js กับ run list/start/pause/resume และ Event explorer ผ่าน typed API client
เพิ่ม polling/backoff, filters, cursor/after_seq และรายละเอียด request/response/log ที่ escaped
แสดง loading/empty/error/session expired และรักษา UI state เมื่อ refresh ตาม api.md
ทำ E2E login → start training S02 → อ่าน event → pause/resume พร้อมหน้าจอ 375/768/1440
```

**ผ่านเมื่อ:** เดิน flow นี้ด้วยข้อมูลจริงได้ทั้ง UI/API เป็น milestone แรกก่อนเพิ่ม AI; controls ที่ยังไม่พร้อมต้องบอกตรงจริง

### 08 — Detection, anomaly และ correlation

- [ ] เสร็จและตรวจรับแล้ว — หลัง 07; SOC-009

```text
ทำข้อ 08: implement versioned rules/anomaly/correlation, detections/evidence และ alerts
ให้ policy สร้าง automatic ticket แบบ idempotent ตาม database.md และแสดงรายการ alert ผ่าน UI
เพิ่ม fixtures/test cases ครบ S01–S05 และ normal traffic โดย detector ไม่อ่าน scenario label/ground truth
ทดสอบ duplicate jobs, cross-run evidence และ S05 ที่ต้องเข้าทาง anomaly จริง
```

**ผ่านเมื่อ:** มีเหตุผล/หลักฐานอ้างได้, soft-deleted automatic ticket ไม่ถูกสร้างใหม่ด้วย correlation เดิม, ไม่สรุป successful compromise จาก blocked request

### 09 — Ticket/Note CRUD, assessment และประวัติ

- [ ] เสร็จและตรวจรับแล้ว — หลัง 08; SOC-010/013

```text
ทำข้อ 09: implement ticket detail/manual create/update/delete/restore, assessment revisions
และ note CRUD/version/evidence พร้อม audit และ expected_version
เชื่อมหน้า investigation จาก prototype กับ API จริง รองรับ 409 โดยไม่ทำ draft หาย
ทดสอบ ownership, cross-run refs, deleted parent, concurrent edit และ run read-only
```

**ผ่านเมื่อ:** ประวัติไม่ถูกเขียนทับ, ผู้เรียนกับ Instructor ใช้สิทธิ์ต่างกัน และ ticket/note mutation ทุกทางถูกล็อกหลัง completing

### 10 — AI pipeline ด้วย mock ที่ทดสอบได้

- [ ] เสร็จและตรวจรับแล้ว — หลัง 09; SOC-011

```text
ทำข้อ 10: สร้าง AnalysisProvider, frozen evidence snapshots, analyses/attempts และ async jobs
เริ่ม mock adapter แบบ deterministic พร้อม Pydantic structured result และ citation/evidence validation
implement GET analysis/retry และ UI statuses โดยแสดง mode=mock ชัดเจน
ทำ quota reservation/reconciliation และ timeout/invalid output/retry tests โดยไม่เรียก provider จริง
```

**ผ่านเมื่อ:** mock ไม่ปนผล benchmark จริง, refs นอก snapshot ถูกปฏิเสธ และ AI ไม่แก้คำตอบของคน

### 11 — Evaluation, completion และ Instructor

- [ ] เสร็จและตรวจรับแล้ว — หลัง 10; SOC-014/015 บางส่วน

```text
ทำข้อ 11: implement finish → completing → completed, pipeline drain และ immutable evaluation snapshot
เพิ่ม deterministic metrics, locked ground truth, JSON export และ Instructor accounts/quotas/comments/review
ตรวจ read-only หลัง finish และไม่ให้ Instructor เขียนทับ assessment/note
ทำ experiment framework A/B/C โดย A/B ใช้ detector จริง และ C unavailable จน provider จริงพร้อม
ทดสอบ cutoff, late AI result, deleted ticket denominator และ N/A metrics
```

**ผ่านเมื่อ:** คะแนนคำนวณจาก snapshot ไม่เปลี่ยนเมื่อมีงานมาช้า, instructor review ตรวจ assignment; ยังไม่อ้างว่าทดลอง C จริงเสร็จในขั้นนี้

### 12 — เชื่อม AI provider จริง

- [ ] เสร็จและตรวจรับแล้ว — หลัง 11; SOC-012/014

```text
ทำข้อ 12: เชื่อม provider/model ที่ฉันเลือกผ่าน adapter เดิม พร้อม runtime secrets และ usage mapping
ถ้ายังไม่ได้เลือก provider/model/งบ ให้เตรียม interface/config/tests ก่อน และถามข้อมูลที่จำเป็นก่อน real calls
เพิ่ม rate limit, timeout, cost caps, retry/idempotency limitations และ unknown-usage reconciliation
เมื่อมีข้อมูลและสิทธิ์พร้อม ทำ bounded smoke test และ experiment C จริง เก็บผลแยกจาก mock
```

**ผ่านเมื่อ:** มีผล real call ที่ตรวจย้อนกลับได้ภายในงบ, provider ล่มไม่หยุด investigation และไม่มี secrets ใน browser/log

### 13 — Knowledge corpus, pgvector และ ingestion

- [ ] เสร็จและตรวจรับแล้ว — หลัง 10; ต่อจาก 12 ตามลำดับแนะนำ; RAG-001/002

```text
ทำข้อ 13 ตาม rag-langchain.md: เพิ่ม kb schema/pgvector, approved Markdown manifest,
chunking, embedding profile, ingestion jobs และ publish/revoke knowledge release
ไม่ index docs ทั้งโฟลเดอร์หรือ private answer key ใช้ fake embeddings ใน CI
สร้าง golden/held-out retrieval tests และ pin release ต่อ run พร้อม dimension/model migration strategy
provider embeddings จริงต้องผ่านการเลือกและงบเช่นเดียวกับข้อ 12
```

**ผ่านเมื่อ:** ingest ซ้ำไม่ duplicate, partial corpus ไม่ถูก publish, retriever role อ่านเฉลยไม่ได้ และ revoke ตัดการใช้งานได้

### 14 — LangChain RAG และ Ask AI

- [ ] เสร็จและตรวจรับแล้ว — หลัง 12/13; RAG-003/004/005

```text
ทำข้อ 14: implement authorized retrieval → LangChain structured generation → citation validation
เชื่อม triage และ ticket questions API/UI พร้อม frozen citations, budgets และ source drawer
รองรับ no_match/unavailable/withdrawn, retry snapshot เดิม และห้าม Ask AI ใน exam ก่อน submit
ทดสอบ cross-run citation, prompt injection, revocation ทุก projection และ finish/question race
ทำ benchmark no-RAG เทียบ RAG ตาม held-out set พร้อมแยกไทย/อังกฤษและต้นทุน
```

**ผ่านเมื่อ:** citation มีจริงและอยู่ใน context, ไม่อ้างว่าคู่มือเป็นหลักฐานของเหตุการณ์; รายงานคุณภาพ/ข้อจำกัดจริง ไม่ใช้ mock เป็นหลักฐานความแม่นยำ

### 15 — Learning path, onboarding และ server-side progress

- [ ] เสร็จและตรวจรับแล้ว — หลัง 04/05; ลำดับแนะนำหลัง 14; LEARN พื้นฐาน

```text
ทำข้อ 15 ตาม learning-path.md: implement learning levels/lessons/progress และ onboarding ใน Next.js
พาอ่าน Method/Path/Response/account/IP/timeline ทีละขั้น เก็บ progress ตาม lesson version ฝั่ง server
เพิ่ม learning path APIs และ prerequisite policy เพื่อเปิดข้อสอบ โดย client ส่ง passed/unlocked เองไม่ได้
Guest อ่าน demo ได้ ทบทวนบทเรียนได้ และ refresh แล้วเรียนต่อได้
```

**ผ่านเมื่อ:** ผู้เรียนใหม่เริ่มต้นถูกระดับ, จบบทเรียนไม่เท่ากับผ่านข้อสอบ, แก้ localStorage/เรียก API ตรงแล้ว bypass gate ไม่ได้

### 16 — Blind exam, immutable submission และ retake

- [ ] เสร็จและตรวจรับแล้ว — หลัง 06/09/11/15; LEARN exam

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

```text
ทำข้อ 17: implement versioned rubric, deterministic checks และ AI/RAG grading หลัง frozen submission
ใช้ grading role แยก private key จาก learner/detector/triage; ไม่ส่งเฉลยเข้า shared knowledge corpus
เก็บ grading revisions/citations/model/knowledge versions; ambiguity/outage/invalid citation เป็น needs_review
เพิ่ม Instructor review/override พร้อมเหตุผล/audit และ atomic level unlock ตาม policy ที่ตกลงไว้
ถ้า rubric หรือผลของ override ต่อ unlock ยังไม่ชัด ให้ถามก่อนกำหนดคะแนนผ่านหรือถอนสิทธิ์เอง
```

**ผ่านเมื่อ:** AI ไม่ปลดล็อกเอง, ผ่านทุกเคสจึงเลื่อนระดับ, override ไม่ลบประวัติ, retake ไม่เขียนทับ attempt เดิม และมี tests submit/grade/unlock races

### 18 — Staging deployment และ operational checks

- [ ] เสร็จและตรวจรับแล้ว — หลัง 17 และ quality gates; SOC-016

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
| 04 | ผ่าน local auth/Guest acceptance | [คู่มือ](auth-development.md), [ผลตรวจ](step-04-verification.md); integration 26, foundation/contract 13, HTTP smoke 3, Chromium E2E 2 และ static/build checks ผ่าน | Branch ข้อ 04 ยังไม่ push/GitHub run; ไม่มี runner/exam/admin CRUD/provider |

ถ้าข้อหนึ่งยังไม่ผ่าน ให้ใช้ prompt ต่อว่า: “แก้ข้อ NN ต่อจากผลทดสอบล่าสุดให้ผ่าน acceptance ที่ยังค้าง โดยไม่เริ่มข้อถัดไปและไม่เปลี่ยน test ให้ยอมรับพฤติกรรมผิด”
