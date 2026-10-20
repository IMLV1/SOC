# แนวทางทำงานใน repository SOC

ใช้กับทั้ง repository อ่านร่วมกับคำสั่งผู้ใช้และเอกสารของงานนั้น ไฟล์นี้เป็นแนวทางพัฒนา ไม่ใช่หลักฐานว่า feature, CI หรือ deployment ผ่านแล้ว

## เริ่มงานและกำหนดขอบเขต

- ตอบและสรุปงานเป็นภาษาไทย โดยคงชื่อ API/identifier ตามโค้ด
- ก่อนแก้ ตรวจ `git status --short --branch`, `git log -5 --oneline`, diff และไฟล์ที่เกี่ยวข้อง รวมไฟล์ untracked อย่าทับงานเดิม
- ตรวจ branch, upstream และ commit ที่กำลังทำจริง อย่าสมมติว่า local `main` ตรง remote หรือโค้ดที่ deploy อยู่ ถ้าผู้ใช้สั่ง pull ให้ตรวจ working tree ก่อนและรักษางานเดิม
- คง branch เดิมเมื่อเหมาะสม ถ้าผู้ใช้ขอ branch ใหม่ ใช้ `codex/<ชื่อสั้นของงาน>` ไม่ switch/reset/stash/force-push หรือลบข้อมูลเพื่อทำให้สถานะสะอาดโดยไม่จำเป็น
- ทำเฉพาะข้อหรือขอบเขตที่ผู้ใช้ระบุ ถ้ามี `docs/implementation-checklist.md` ให้ใช้ acceptance ของข้อนั้น ไม่ถือว่าการอ่าน roadmap อนุญาตให้ทำทุก phase
- ตรวจว่าไฟล์และเครื่องมือมีจริงใน checkout ก่อนใช้คำสั่ง ถ้า checklist/SRS/OpenAPI หรือ scaffold ขาด ให้แจ้งพร้อมตรวจประวัติที่เกี่ยวข้อง อย่าสร้าง scaffold ทับงานเดิมหรือคัดลอก implementation ทั้ง branch เพื่อแก้ปัญหาเฉพาะจุด
- เมื่อ checkout เปลี่ยนระหว่างทำงาน ให้ตรวจสถานะใหม่ก่อนเขียน ไม่ย้อนการเปลี่ยนของผู้ใช้เอง
- ทำ implementation, migration, API, UI และ regression tests ให้ครบในขอบเขตที่รับงาน ไม่เพิ่มบริการหรือ feature นอกขอบเขตเพื่อให้หน้าจอดูครบ

## เอกสารและวิธีแก้ข้อขัดแย้ง

เริ่มจาก [สารบัญ](docs/README.md) แล้วอ่านเอกสารที่เกี่ยวข้องให้ครบ รวมไฟล์เพิ่มเติมใน `docs/` ที่เกิดขึ้นภายหลัง:

| เอกสาร | ใช้กำหนด |
|---|---|
| [soc-simulation.md](docs/soc-simulation.md) | เป้าหมาย SOC จำลอง, S01–S05, acceptance และงานส่งรายวิชา |
| [learning-path.md](docs/learning-path.md) | บทเรียน, server-side progress/gate, exam, feedback และ retake |
| [architecture.md](docs/architecture.md) | ขอบเขต API/worker/frontend, clock, queue, AI และ evaluation |
| [api.md](docs/api.md) | endpoint, payload, status, permissions, pagination, concurrency และ UI integration |
| [database.md](docs/database.md) | constraints, transactions, roles, migrations, snapshots และ retention |
| [rag-langchain.md](docs/rag-langchain.md) | approved corpus, ingestion, retrieval, citations, revocation และ benchmark |
| [ci-cd.md](docs/ci-cd.md) | checks, artifacts, environment, deploy/migrate/rollback และ recovery |
| [development-plan.md](docs/development-plan.md) | dependencies, backlog, test strategy และ Definition of Done |
| [prototype-alignment.md](docs/prototype-alignment.md) | flow อ้างอิงและข้อจำกัดของ prototype |

เมื่อมี `docs/srs.md`, `docs/openapi.yaml`, คู่มือ local/CI และรายงาน `docs/step-*-verification.md` ให้อ่านร่วมกัน: SRS เป็นที่บันทึก policy/decision register, OpenAPI แยก approved/draft และรายงานเป็นหลักฐานเฉพาะวันที่/commit/environment ที่ตรวจ

- คำสั่งและข้อยืนยันของผู้ใช้มีผลเหนือข้อเสนอเก่าในเอกสาร ใช้ข้อตกลงที่อนุมัติแล้วต่อ ไม่ถามซ้ำโดยไม่มีข้อมูลใหม่
- ห้ามเลือกสิทธิ์ คะแนน rubric retake หรือ override/revoke unlock เองเมื่อเอกสารขัดกัน ระบุไฟล์/หัวข้อและข้อสรุปที่เสนอ แล้วถามเฉพาะส่วนที่ยังต้องตัดสินใจ ทำงานส่วนที่ไม่ขึ้นกับคำตอบต่อได้
- แยกข้อกำหนดออกจากสถานะ implementation: หัวเอกสารเก่าที่บอกว่ายังไม่มี backend และรายงานว่า local ผ่าน ไม่ใช่หลักฐานของสถานะปัจจุบัน ให้ตรวจโค้ด/tests/commit จริง
- เลข migration ในแผนเป็นตัวอย่าง ไม่ใช่เลข revision ที่ต้องใช้ ตรวจ Alembic graph จริงก่อนสร้าง revision ใหม่
- ไม่อัปเดตสถานะทั้งแผนจากการแก้ feature เดียว ไม่เปลี่ยน draft เป็น approved เพียงเพราะสร้าง schema ได้

## Stack และขอบเขตข้อมูล

- ใช้ Next.js App Router + TypeScript, FastAPI + Python/Pydantic, PostgreSQL, SQLAlchemy async/asyncpg และ Alembic
- ใช้ modular monolith แยก API, Python worker และ evaluator ตามสิทธิ์ งาน background ใช้ durable PostgreSQL jobs ไม่ใช้ browser timer หรือ FastAPI BackgroundTasks แทน queue และไม่เริ่ม runner ซ้ำในทุก Uvicorn process
- FastAPI เป็นเจ้าของ auth และ domain `/api/v1`; Next.js ใช้ typed client ผ่าน same-origin proxy ไม่สร้าง business API ซ้ำใน Route Handlers/Server Actions
- เก็บ `prototype/` เป็น reference ไม่ย้ายทับ frontend ใหม่ ไม่ใช้ localStorage เป็นฐานข้อมูล/session/คะแนน/progress/unlock จริง เก็บได้เฉพาะ UI preferences ที่ไม่ใช่สิทธิ์หรือข้อมูล authoritative
- ใช้ fixture จำลองเท่านั้น ไม่เชื่อม SIEM/EDR ไม่ยิง exploit/URL ตามคำสั่ง browser และไม่ให้ AI สั่ง block/disable ระบบจริง
- ปัก runtime/package versions ตามไฟล์ pin, manifests และ lockfiles ที่ตรวจจริง ใช้ `npm ci`/`uv sync --frozen` เมื่อมี tooling แล้ว ไม่แก้ lockfile ด้วยมือหรืออัปเกรดเป็น latest โดยไม่มีงานรองรับ

## API, authentication และ UI

- JSON ใช้ snake_case, UUID, เวลา UTC และ envelope/error ตาม contract; Pydantic ปฏิเสธ unknown fields และใช้ explicit response allowlists
- ใช้ opaque session cookie, HttpOnly/Secure/SameSite, hash-only storage, expiry/revocation และ password hashing ผ่านไลบรารี ตรวจ CSRF + Origin ทุก mutation ตาม contract รวม login/register
- สมัครได้ Analyst เท่านั้นและไม่ auto-login; Instructor provision ฝั่ง server ไม่รับ role/owner/quota/score/passed/unlocked จาก client เป็นข้อมูลที่เชื่อถือได้
- ตรวจ owner/role/assignment ฝั่ง server ทุกทาง รวมก่อนอ่าน idempotency cache; Instructor ไม่ได้สิทธิ์อ่านทุกบัญชีจาก role เพียงอย่างเดียว
- ปฏิเสธ resource นอก scope ด้วย 404; ใช้ 401/403/409/422/429 ตาม contract ไม่เผย input, SQL, stack trace หรือ secrets ใน errors
- การแก้ข้อมูลใช้ `expected_version` พร้อม history/audit ใน transaction เดียว; create/retry ใช้ idempotency ตาม operation, key เดิม/body ต่างต้อง conflict
- ใช้ cursor/filter และ `after_seq` ตาม contract ไม่ปน pagination modes; polling มี backoff และจัดการ stale response, hidden tab และ session expired
- แสดง loading/empty/error/pending/unavailable/mock/real ตรงจริง เก็บ draft เมื่อ 409 และคง UI state เมื่อ refresh ตาม contract
- แสดง log, request/response, note และ citation เป็น escaped text; ไม่ render untrusted HTML ไม่ shared-cache ข้อมูลสมาชิกข้าม session
- ตรวจ UI ที่ 375/768/1440px, keyboard focus และ labels สีต้องมีข้อความประกอบ ปุ่มที่ยังไม่พร้อมต้องบอกข้อจำกัด ไม่อ้างพร้อมเพราะมีหน้าจอ

## Training, exam และข้อตกลงที่ผู้ใช้ยืนยันแล้ว

ข้อเหล่านี้มาจากการตัดสินใจของผู้ใช้ ไม่ใช่การอนุมัติ exam endpoints หรือ rubric ที่ยังขาด:

- Instructor อ่านเฉลย **ข้อสอบหลัง submit เท่านั้น** และต้องอยู่ใน assignment scope พร้อม access audit
- ผู้เรียนได้เฉพาะ feedback ตาม rubric ไม่มี full exam answer key แม้ result finalized หรือ run completed; training truth ใช้ policy แยกตาม SRS/approved contract
- Ticket disposition คง `true_positive|false_positive|undetermined` ไว้ก่อน ไม่เพิ่ม `benign_positive` จากตัวอย่างในเอกสารเก่าจน scoring contract ได้ข้อสรุป
- โควตาผู้สมัครใหม่คือ 10 training runs และ 20 logical AI requests ต่อวัน UTC ไม่ใช่การเลือก quota/retake ของ exam

Server กำหนด run mode และเลือก exam case หลังตรวจ lesson/level gate; demo/training fixtures แยกจาก exam bank การจบบทเรียนไม่เท่ากับสอบผ่าน การ retake สร้าง attempt ใหม่

กำหนด blind exam serializers ก่อนเปิด endpoints จริง ใช้ allowlist แยกจาก training DTO ไม่ serialize training payload แล้วค่อยลบ field ตรวจทุก surface รวม list/overview/alerts/tickets/history/audit/analysis/sources/export/cache/errors ห้ามหลุด initial severity, detector hints, AI brief, private labels, rubric ที่เป็นคำใบ้ หรือ future schedule

`finish` ใช้ training; exam ใช้ atomic/idempotent `submit` ที่ freeze คำตอบและ evidence/run cutoff พร้อมกัน การปล่อย event ครบหรือ generic finish ต้องไม่ bypass submit/grading ก่อน submit ห้าม triage/Ask AI ช่วยตอบ; หลัง freeze ห้าม retry/question mutation ผ่าน training routes

Rubric, คะแนนผ่าน, evidence completeness, active-attempt/retake/expiry policy, feedback disclosure detail และผล override ต่อ unlock ต้องได้ข้อสรุปก่อนเปิดใช้งานจริง Grading ใช้ role แยกหลัง frozen submission, เก็บ revisions และไป `needs_review` เมื่อกำกวม/provider ล่ม/citation ผิด ไม่ auto-pass จาก AI หรือความยาวคำตอบ

## Transactions, runner และ evaluation

- ใช้ AsyncSession แยกต่อ request/job และ bound parameters; constraints/composite FKs บังคับ evidence/retry refs อยู่ใน run เดียวกัน
- ใช้ลำดับ lock เดียวกับ SRS เมื่อมี: user/progression guard → idempotency → run → attempt → ticket/resource/revision → quota ledgers/reservations → insert jobs/audit/cache แล้ว commit เรียง keys คงที่เมื่อแตะหลายแถว ใช้เฉพาะ subset ที่ operation ต้องใช้ ไม่ย้อนลำดับ
- create run ที่ยังไม่มีแถว visible ใช้ guard/idempotency → quota → insert run/attempt ได้; ไม่ใช้ข้อยกเว้นนี้กับการ lock existing run
- claim jobs ด้วย SKIP LOCKED/lease ใน transaction สั้นแยกจาก domain work; ไม่ถือ job lock แล้วรอ run ตรวจ lease token/expiry ก่อน heartbeat และ commit ผลเพื่อกัน stale worker
- release/pause/finish ใช้ run lock เดียวกัน เวลาอิง DB; หลัง pause สำเร็จไม่มี future events ใหม่ logout/ปิด browser ไม่หยุด runner restart ต้องไม่ซ้ำด้วย unique keys/dedupe
- external network/provider calls อยู่นอก DB transaction; queue เป็น at-least-once ไม่อ้าง exactly-once ของ provider ภายนอก
- Automatic ticket unique ตาม run/correlation **รวม soft-deleted rows**; evidence ใหม่ไม่สร้างเคสเดิมซ้ำหรือ restore เอง
- Assessment/note revisions และ audit เป็น append-only ตามหน้าที่ Instructor comments แยกจากคำตอบของผู้เรียน ห้ามเขียนทับ assessment/note ของผู้อื่น
- `completing/completed/failed` ล็อก ticket/note/assessment mutations รวม restore ตาม policy; finish freeze cutoffs, drain bounded สูงสุด 60 วินาที และสร้าง immutable evaluation snapshot งานมาช้าไม่เปลี่ยนผลเดิม
- Detector อ่านเฉพาะ released evidence ไม่อ่าน scenario label/ground truth; ทดสอบ S01–S05 และ normal traffic โดย S05 ต้องผ่าน anomaly จริง blocked request ไม่ยืนยัน successful compromise
- Metrics อิง frozen dataset/config และ incident/group, ไม่ใช้การลบ ticket เปลี่ยน denominator ตัวหารศูนย์เป็น null/N/A พร้อมเหตุผล แยก human score, detector metrics และ AI quality
- A ใช้ rules จริง, B ใช้ rules/anomaly จริง, C เพิ่ม real AI บน dataset/config เดียวกับ B เก็บ experiment outputs แยกจาก live run; C unavailable จน provider/budget พร้อม ไม่ใช้ mock อ้างผล C จริง

## Database, migrations และ secrets

- Runtime ไม่ใช้ owner/superuser แยก api/worker/evaluator/migration/retention credentials; detector/triage/retriever ไม่มีสิทธิ์อ่าน private truth
- เพิ่ม migration ใหม่ ไม่แก้ revision ที่ใช้งานแล้ว ไม่แก้ checksum ledger เพื่อหลบ drift; ใช้ migration wrapper ที่ถือ advisory lock/ledger เมื่อมี ไม่ข้ามไป direct Alembic
- Migration/seed/provision เป็น operator/one-shot ไม่รันใน API startup; ทดสอบ fresh migration, upgrade, grants, constraints และความเข้ากันได้กับ release เดิมตามงาน
- แยก artifacts: frontend ไม่มี backend fixtures/เฉลย, API ไม่รับ future schedules, worker ไม่มี private truth; privileged seed/evaluator ใช้เฉพาะข้อมูลที่จำเป็น
- ห้าม default password/key หรือ secrets ใน repo, `.env.example`, browser/NEXT_PUBLIC, logs, screenshots หรือ CI artifacts ใช้ ignored local files/runtime secret store และอย่าพิมพ์เนื้อหา `.env` หรือ secret files เพื่อ debug
- Database tests ใช้ฐานทิ้งได้และ runtime roles จริง ตรวจชื่อฐาน/opt-in reset ตาม harness ก่อนล้าง ห้าม cleanup volumes ของระบบผู้ใช้เพื่อให้ tests ผ่าน

## AI provider และ RAG

- CI/default development ใช้ deterministic mock/fake adapters พร้อม mode ชัดเจน Validate structured result และ citations เป็น subset ของ frozen evidence/retrieval snapshot ไม่ fallback เป็นข้อความดิบเมื่อ validation ล้ม
- Provider outage/timeout/invalid output ไม่หยุด investigation และไม่แปลว่าไม่มีภัย AI ไม่แก้ human assessment หรือปลดล็อกระดับเอง
- Reserve quota/cost ก่อน dispatch แบบ atomic; แยก logical requests กับ provider attempts/component usage, timeout ที่ไม่ทราบ usage คง `unknown` hold จน reconcile ไม่เดาว่าใช้ 0 และไม่ retry แบบเสี่ยงใช้เงินซ้ำโดยไม่มี policy
- ทิศทาง provider ปัจจุบันคือ Dify API เท่านั้น; ห้ามเรียก Gemini โดยตรง. Gemini calls/caps ในรายงานเก่าเป็นประวัติ ไม่ใช่สิทธิ์ใช้งานปัจจุบัน. Dify ยังปิดจนกว่าจะกำหนด app/workflow, citation/revocation/usage contract, ค่าใช้จ่าย และ secret config ชัดเจน; ห้าม real calls ก่อนนั้น
- RAG เป้าหมายใช้ Dify ภายนอกผ่าน API; ห้ามอ้าง pipeline LangChain/pgvector เดิมว่าเป็น Dify. เมื่อเชื่อม ให้ตรวจ authorized retrieval/citations/revocation, ไม่มี LLM tools/shell/SQL execution หรือ public URL/file ingestion
- **ห้าม index `docs/` ทั้งโฟลเดอร์**, prototype, private truth, future schedules หรือ benchmark answers ใช้ approved Markdown manifest/reviewer/hash และ corpus แยกเท่านั้น
- Ingestion/version/profile/dimension ผ่าน migrations และ jobs; validate ครบก่อน publish immutable release, pin release/config ต่อ run, retry ใช้ snapshot เดิม ไม่เปลี่ยน corpus เงียบ ๆ
- ตรวจ revocation ก่อน retrieval/provider/persist/read ทุก projection; withdrawn result ต้องไม่กลับมาทาง ticket/export/admin/cache และ citation ถูกถอนต้องปฏิเสธตาม contract
- Knowledge citation เป็นหลักการ ไม่ใช่หลักฐานว่าเหตุการณ์สำเร็จ no_match ไม่เรียก chat สำหรับ question; แยก fake regression จาก held-out Thai/English benchmark จริง พร้อม sample count/config/usage และข้อจำกัด

## การตรวจงานและส่งมอบ

เลือก checks ตามสิ่งที่แก้และ tooling ที่มีจริง คำสั่งด้านล่างไม่ใช่คำสั่งให้สร้างไฟล์/ติดตั้งระบบที่ขาดโดยอัตโนมัติ:

| ส่วน | คำสั่ง/การตรวจเมื่อมี implementation |
|---|---|
| Prototype จาก root | `node --check prototype/app.js`, `node --check prototype/model.js`, `node --check prototype/server.cjs`, `npm --prefix prototype test` |
| Backend จาก `backend/` | `uv sync --frozen`, `uv run --frozen ruff check app tests migrations ../scripts`, `uv run --frozen ruff format --check app tests migrations ../scripts`, `uv run --frozen mypy app`, `uv run --frozen pytest -m 'not integration'` |
| Contract จาก `backend/` | `uv run --frozen python -m openapi_spec_validator ../docs/openapi.yaml`, approved FastAPI drift tests และ `uv run --frozen python ../scripts/generate-client-types.py --check` |
| Frontend จาก `frontend/` | `npm ci`, `npm run lint`, `npm run typecheck`, `npm run build`, `node --test tests/assets.test.mjs`; HTTP smoke/E2E ต้องเปิด stack แยกก่อน |
| Integration จาก root ใน Bash | `COMPOSE_PROJECT_NAME=soc-ci-<unique-task> bash scripts/ci-compose.sh` เมื่อมี script; ตรวจว่า project ทิ้งได้ เพราะ cleanup ลบ volumes ของ project นั้น |
| เอกสาร | ตรวจ local links ด้วย script ของ repo ถ้ามี และ `git diff --check`; งานเอกสารล้วนไม่ต้องอ้างว่าทดสอบ runtime ใหม่ |

- เพิ่ม regression ของ feature ใหม่ใน CI ต่อเนื่อง ใช้ PostgreSQL จริงตรวจ concurrency/locks/fencing/permissions ไม่ใช้ mocks อ้างผล race ผ่าน
- ตรวจ browser assets หลัง production build เมื่อแตะ client/imports ถ้า leakage guard fail ให้หาต้นเหตุ ไม่ปิด assertion หรือย้ายเฉลยไป public API เพื่อหลบ bundle test
- ไม่เพิ่ม timeout/sleep, skip, continue-on-error หรือลด assertions เพื่อกลบ bug; แก้ test ได้เมื่อพิสูจน์ว่าความคาดหวังผิด contract และคงตรวจพฤติกรรมสำคัญ
- แยก local checks, GitHub CI ของ SHA ล่าสุด, branch protection และ deployed acceptance ถ้ายังไม่รัน GitHub ให้ระบุ “รอยืนยันบน GitHub”; YAML ไม่พิสูจน์ว่าตั้ง required checks แล้ว
- ติ๊ก checklist เฉพาะ acceptance ที่ทดสอบผ่านจริง บันทึกคำสั่ง, ผล, commit/environment และสิ่งที่ยังค้าง ไม่อ้าง mock เป็น benchmark หรือ targets เป็นผลวัด
- สรุปไฟล์ที่แก้ เหตุผล วิธีเปิดทดสอบ ผลตรวจ และข้อจำกัดให้ผู้ใช้; PR อธิบาย final behavior และ validation ไม่สร้าง review/ผู้ร่วมงาน/ประวัติปลอม
- ก่อน commit ตรวจ diff และ stage เฉพาะไฟล์งาน ห้าม `git add .` จนรวม secrets/untracked ที่ไม่เกี่ยวข้องเข้าไป

## GitHub และ deployment

ดำเนินการ commit/push/PR/merge/deploy ตามขอบเขตที่ผู้ใช้อนุญาตแล้ว ไม่ขอซ้ำเมื่อมีสิทธิ์ชัดเจน แต่การให้แก้โค้ดอย่างเดียวไม่ใช่การอนุญาต publish, ซื้อบริการ หรือเปิด provider เสียเงิน

ก่อนรายงาน deployment ตรวจ source SHA/branch, CI, environment, migrations, worker/evaluator และ health ของบริการจริง Auto-deploy อัปเดตโค้ดตาม config; ไม่ได้เพิ่ม worker เปลี่ยน secrets หรือ migrate DB ให้เองทุกระบบ Free auth-only preview ไม่เท่ากับ training/AI/production พร้อม

อย่าเปิด run controls ให้ enqueue งานที่ไม่มี worker รองรับ ตรวจ HTTPS/cookie/CSRF และ flow จริงบน URL เมื่อ deploy อยู่ใน scope; production ต้องมี release/rollback/backup-restore ตาม policy ที่อนุมัติ แยก migration one-shot จาก runtime และไม่อ้างว่าข้อ deployment ผ่านจากการเปิดหน้าเว็บได้เท่านั้น
