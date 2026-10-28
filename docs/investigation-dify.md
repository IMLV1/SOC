# Investigation Dify — code support และสถานะเปิดใช้

อัปเดต 28 ต.ค. 2026 บน branch `codex/friend-runtime`, base SHA `29dace8`
พร้อม working-tree changes; ไม่ใช่การอนุมัติ production หรือการ Publish Flow

## พฤติกรรมที่เพิ่มในโค้ด

- Worker เลือก `DifyInvestigationProvider` เมื่อ real run pin ตรงกับ reviewed release
  ใช้เฉพาะ frozen/released training evidence, redact ก่อนส่ง, จำกัด 50 events,
  32,000 UTF-8 bytes และ output ceiling 2,048 tokens ตาม DSL
- ตรวจ Workflow ID หลังตอบกลับ, contract version, structured schema และ event citations
  ไม่รับ raw-text fallback, knowledge refs, reasoning tags หรือ omitted snapshot
- Pin non-secret release snapshot และ canonical SHA-256 ใน `run_versions.config_snapshot`
  ตั้งแต่ start; retry ใช้ run pin เดิม ไม่เปลี่ยนไป Workflow/config ใหม่
- Config ไม่ครบ/ยังเป็น draft: create training run คืน 503 ก่อนสร้าง run/jobs
  Exam บังคับ mock/no-AI โดยไม่อ่าน investigation credentials
- Worker ตรวจ release ก่อน dispatch และ persist; หน้า detail/list/idempotent replay
  รวม evaluation snapshot/export ซ่อนผลเมื่อ release เปลี่ยน ถูกถอน หรือพบ version drift
  ไม่แก้ immutable evaluation/metrics ที่บันทึกไปแล้ว
- Persist unknown USD hold พร้อม provider admission ก่อน network ใน transaction ที่ fenced
  crash หลัง admission, timeout หรือ lost lease ไม่ dispatch ซ้ำเมื่อ job ถูก claim ใหม่
  คำตอบที่มาช้าจาก stale worker ไม่ persist; จึงอาจสูญผลแต่ไม่ส่งซ้ำเสี่ยงคิดเงิน
- `total_tokens=null` คือไม่ทราบ usage; ไม่แต่ง input/output token split
  `pricing_tier=verified_bound` ระบุว่าอิง reviewed ceiling ไม่ใช่ actual bill/free-tier assertion
  known zero แยกจาก unknown; invalid output ที่มี usage ยังลงบัญชีตามข้อมูลจริง
- Tutor และ investigation จับ advisory lock เดียวกันและรวม USD commitments
  ใช้ daily ceiling จาก Tutor policy เดิม ไม่เพิ่มเพดานหรือเปลี่ยน policy ในงานนี้
  unknown holds ข้ามวัน UTC ยังนับจน reconcile; completed known calls นับเต็ม call ceiling
- Migration ใหม่ `0024_investigation_budget` เพิ่ม accounting table และ grants
  API/evaluator อ่าน metadata ได้; worker insert และ update เฉพาะ settlement columns
  Runtime แก้ reserved USD ไม่ได้ ไม่แก้ revision/checksum เดิม

ไม่มี business endpoint ใหม่ และไม่เปลี่ยน learner scores, assessment, unlock, exam rubric
Transport สำหรับ investigation นี้เป็น structured triage จากเหตุการณ์ ไม่ได้เปิด legacy
RAG/Ask AI question pipeline, experiments C หรือ exam grading โดยอัตโนมัติ

## Review file และ key แยกจาก Tutor

เริ่มจาก `knowledge/dify/investigation-review.pending.json` ซึ่งตั้งใจให้ validation ไม่ผ่าน
operator ต้องนำเข้าตรวจ `SOC-investigation-draft.yml` ใน App แยก ยืนยัน Workflow ID,
model/plan, input/output, ไม่มี tools/hidden retrieval, max input/output และค่าใช้จ่ายจริง
ก่อนเก็บ reviewed JSON ที่มี `status=approved_for_investigation`, reviewer,
`cost_bound_verified=true` และ positive `call_bound_usd` ที่ตรวจแล้ว
ไม่เลือกตัวเลขค่าใช้จ่ายหรืออ้าง Free ให้จากชื่อโมเดลใน draft

เก็บ release JSON และ separate App key ใน ignored `.local/` หรือ runtime secret store
อย่าส่ง key ในแชต, frontend, Git หรือ logs; worker ปฏิเสธ key เดียวกับ Tutor
release snapshot ที่อยู่ใน DB ไม่มี key หรือ host secret-file path
การถอน release ทำได้ด้วยการถอน/เปลี่ยน reviewed file ที่ mount ให้ runtime ทุกตัว
จึงต้องจัดส่ง config เดียวกันแบบ operator-controlled ให้ API/worker/evaluator

Published-latest ตรวจ version หลัง dispatch เท่านั้น ไม่เทียบเท่า pinned execution
หากเผยแพร่ Workflow รุ่นใหม่ ครั้งแรกอาจเรียกไปแล้วก่อนตรวจ mismatch
ระบบเก็บ unknown hold และหยุดงานใหม่ของ release นั้นจน operator review ใหม่

## เตรียม runtime หลังได้รับอนุมัติเท่านั้น

ยังไม่ได้ใช้ overlay นี้กับ `soc-friend` ในงานนี้:

- `DIFY_ANALYSIS_RELEASE_HOST_FILE`: path ของ reviewed private JSON
- `DIFY_ANALYSIS_KEY_HOST_FILE`: path ของ separate investigation App key
- เพิ่ม `-f compose.investigation.yaml` เป็นไฟล์สุดท้ายของ Compose stack
  overlay เปิด provider เฉพาะ API/worker, mount review ให้ evaluator และ mount key เฉพาะ worker
  ไม่มี operator services หรือพอร์ตสาธารณะเพิ่ม
- ต้อง migrate 0024 ผ่าน migration wrapper โดย operator ก่อนใช้ image ใหม่
  ใช้คู่มือ migration/release เดิม; ชุด friend runtime ไม่มี owner/admin credentials
  **ห้าม migrate/seed/reset Supabase ที่ใช้งานร่วมกันเอง**

Default Compose ยังคง mock สำหรับ investigation และ Tutor จริงทำงานแยกเหมือนเดิม
ไม่มีการ Publish/เปลี่ยน Flow, rotate secrets, เปิด provider investigation หรือ deploy ในงานโค้ดนี้

## การตรวจ

Tests ใช้ deterministic HTTP/provider fixtures และ PostgreSQL ทิ้งได้
`soc_test_investigation_code` บน internal Docker network, tmpfs และ runtime roles จริง
ไม่ได้ใช้ managed Supabase หรือเรียก Dify/Gemini จริง

คำสั่งหลักจาก backend ตาม dependencies ที่ pin ไว้:

```bash
uv run --frozen pytest -m 'not integration' -q
uv run --frozen pytest tests --ignore=tests/test_foundation.py -m integration -q
uv run --frozen ruff check app tests migrations ../scripts
uv run --frozen ruff format --check app tests migrations ../scripts
uv run --frozen mypy app
```

Integration ใช้ `SOC_TEST_DB_NAME=soc_test_*`, isolated role secrets และ
`SOC_TEST_ALLOW_RESET=yes` ตาม harness เท่านั้น ห้ามชี้คำสั่งไปฐานจริง
ผลตรวจ local บน source ปัจจุบัน ใช้ Python 3.12.14/dependencies ใน cached image
`soc-ci-exam-ai-20261028-test:latest` และ mount source read-only:

- Non-integration: **212 passed**, 115 integration cases deselected
- Integration รอบหลักทั้งชุด (ยกเว้น foundation ตาม CI script): **110 passed,
  1 skipped**; รายการที่ข้ามคือ live Dify opt-in เดิม ไม่ได้เพิ่ม skip
- หลังเพิ่มเคส lost lease/revocation ระหว่าง dispatch/shared-budget race และ snapshot
  รัน investigation integration รอบสุดท้าย **11 passed** บน runtime roles จริง
- Fresh migrations/repeat/concurrent migration/checksum/grants tests อยู่ใน suite
  PostgreSQL ทิ้งได้ข้างต้น; ไม่ migrate ฐานร่วมและไม่แก้ ledger เดิม
- Ruff check/format ทั้ง backend/tests/migrations/scripts ผ่าน 185 files,
  mypy `app` ผ่าน 105 source files, OpenAPI validator และ generated-client `--check` ผ่าน
- Compose รวม investigation overlay `config --quiet`, local Markdown links
  และ `git diff --check` ผ่าน; overlay validation ใช้ไฟล์ทดสอบ ไม่มีการ up stack ใหม่
- API/worker/evaluator ของ `soc-friend` เดิมยัง healthy ไม่ rebuild ด้วยโค้ด migration ใหม่
- Build images แยก `soc-investigation-api:review` และ `soc-investigation-runner:review`
  สำเร็จ; ตรวจ imports/graph head 0024 และ artifact isolation ด้วย containers
  `--network none --read-only` ผ่าน ไม่มี credentials/ฐานข้อมูลใน build/smoke process
  ยังไม่สลับ images ของบริการเดิมและไม่ push images

GitHub CI **รอยืนยันบน GitHub**
ยังไม่ได้ import/execute draft บน Dify หรือทำ live investigation smoke/quality benchmark

Lesson Tutor เคยผ่าน live smoke หนึ่งคำถาม: 2,857 tokens/citations 4 รายการ
และ history คงอยู่หลัง refresh เป็นผล Tutor เท่านั้น ไม่ใช่ investigation acceptance

อ้างอิง: [Dify API](https://docs.dify.ai/en/api-reference/guides/get-started)
และ [Workflow Studio](https://dify.ai/workflows)
