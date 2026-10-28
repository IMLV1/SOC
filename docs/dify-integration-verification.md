# Dify lesson tutor — ขอบเขตและผลตรวจ 28 ต.ค. 2026

Working tree หลัง `a1fc962` ยังไม่ commit/push และไม่ใช่ production release

**สถานะล่าสุด 28 ต.ค. 2026:** ผู้ใช้อนุมัติใช้ Published ล่าสุดบน Dify Free แทน pinned execution แล้ว เปิด lesson Tutor บน local Supabase stack ด้วย policy version 2 ดูรายงานรอบเปิดด้านล่าง ประวัติคำว่า disabled/pinned ในรายงานเก่าไม่ใช่สถานะปัจจุบัน

## เชื่อมอะไรในรอบนี้

- `app/knowledge/dify_workflow.py`: `/workflows/run`, `inputs.question`, blocking, ตรวจ response workflow_id เทียบรุ่นที่อนุมัติ ไม่มี retries/redirects อัตโนมัติ ไม่เรียกโมเดลโดยตรง
- migration `0023_dify_tutor`: `tutor_policy`, `tutor_questions`, status/30-day expiry/cost holds/indexes และ least-privilege grants เพิ่มใหม่ ไม่แก้ revision ที่ใช้แล้ว
- `app/tutor/`: API admission/owner/history, durable job, lease/fencing, pinned Workflow/corpus version, citations และ source content hashes
- หน้าบทเรียนมีคำถาม/สถานะ/ประวัติจาก DB; ไม่ใช้ localStorage และไม่เปิดผู้ช่วยระหว่างมี exam ค้าง
- `compose.dify.yaml` เป็น overlay mount secret เฉพาะ API/worker ไม่ใส่ key ใน frontend และไม่เปิด policy โดยอัตโนมัติ
- Budget รวม US$0.25/วัน UTC; release นี้ reserve US$0.001/คำถามเป็น conservative accounting ceiling ภายใต้ Groq Free + Full Text/no rerank ที่ตรวจแล้ว ไม่ใช่ยอดเงินจริง หากทราบผลและ token usage ให้ account เต็ม ceiling ในวันนั้น ไม่คืนเป็น 0; unknown holds ข้ามวันยังนับจน reconcile

## Endpoint ใหม่ (implementation contract ยังไม่เลื่อน OpenAPI draft)

| Method | Path | หน้าที่ |
|---|---|---|
| GET | `/api/v1/tutor/availability` | Analyst session, บอก available/reason และเพดาน |
| POST | `/api/v1/tutor/questions` | `lesson_id`, `question` ≤2000; CSRF/Origin + Idempotency-Key; owner/lesson gate/no exam; reserve quota+budget+enqueue ใน transaction เดียว; 202 |
| GET | `/api/v1/tutor/questions` | ประวัติล่าสุดไม่เกิน 20 ของ owner ที่ยังไม่หมดอายุ; ปิดระหว่างสอบ |
| GET | `/api/v1/tutor/questions/{id}` | owner-only, 404 ข้ามบัญชี; ปิดระหว่างสอบ; ถอนแหล่งแล้ว result=null |

Default policy disabled คงให้บทเรียน/ฝึก/สอบทำงาน ไม่สร้างงานที่สัญญาว่าใช้ AI ได้จน worker/contract พร้อม

## Output ที่ Dify ต้องส่ง

ใน Output node ตั้งสองค่า:

1. `answer` = LLM → text
2. `sources` = Knowledge Retrieval → result (array ดั้งเดิม ไม่ใช่ LLM แต่ง sources เอง)

Source ต้องมี `title`, `content`, `metadata.document_id` ที่อยู่ใน release ที่ผู้ดูแลรับรอง
Chunk ต้องมี heading SOC-xxx ที่อ่านเข้าใจ และ hash ของ content ต้องอยู่ใน approved immutable chunk list
Answer ต้องอ้าง SOC-xxx ที่มีใน snapshot จริง URL ที่ไม่อยู่ใน retrieved content ถูกปฏิเสธ
นี่ตรวจโครงสร้าง/การมีอยู่ของแหล่ง ไม่พิสูจน์ว่าทุกข้อความที่โมเดลสรุปถูกต้องเชิงความหมาย

## Gate ก่อนเปิด live

- ผู้ใช้อนุมัติงบ US$0.25/วันแล้ว แต่ยังต้องตรวจ per-call cost bound: รุ่นโมเดล, max output/thinking, จำนวน nodes, retrieved context, embedding/reranker cost และปิด tools ที่ไม่จำเป็น
- ถ้าค้นไม่พบ ให้ flow แยกทางคืน insufficient context โดยไม่เรียก LLM อย่าใช้ prompt อย่างเดียวแทนเงื่อนไขนี้
- Publish flow ที่มี sources แล้ว pin version ใหม่; version ที่ smoke เดิมส่งเพียง answer จึงไม่เปิดเป็น production adapter เงียบ ๆ
- Corpus ต้องมี reviewer จริง/version/chunk hashes และข้อกำหนดถอนเอกสาร; manifest ใหม่ยัง pending content review ไม่ปลอมชื่อ reviewer
- ตรวจความพร้อม worker และ secret read-only mount ภายใต้ runtime UID จริง ก่อน operator อนุมัติ policy
- Usage รวมยังไม่สามารถสรุปค่าใช้จ่ายจาก total_tokens เพียงค่าเดียว คง unknown reservation จน reconcile ค่า generation + retrieval/embedding; ยังไม่มี operator UI สำหรับ reconciliation
- ปรับ release/policy ต้องถอนผลเก่าที่ source ไม่อยู่ใน allowlist และตรวจ projection ทุกทาง ไม่มี export/admin endpoint ของ Tutor ในรอบนี้

## หลักฐาน live ที่มีอยู่ก่อนเชื่อม UI

ผู้ใช้อนุญาต smoke test 1 ครั้ง: `/info` และ `/parameters` HTTP 200, app SOC mode workflow, input question required
`/workflows/run` HTTP 200/succeeded, ประมาณ 6.8 วินาที, reported 1,243 tokens, outputs มี answer เท่านั้น ไม่มี sources
ไม่ใช่ end-to-end UI/DB acceptance หรือผล benchmark และยังไม่ได้ตรวจค่าเงินจริงจากใบแจ้งใช้
รอบ implementation ใช้ fake provider สำหรับ regression ไม่เรียก Dify เพิ่มระหว่างรอ gate

## ผลตรวจอัตโนมัติ

- Backend: Ruff check/format, mypy 101 modules ผ่าน; `pytest -q -p no:cacheprovider` **262 passed** บน PostgreSQL tmpfs ชื่อ `soc_test_dify_20261028` ใช้ runtime roles จริง/fake provider ไม่เรียก Dify; generated client types check ผ่าน
- ครอบคลุม concurrent reservation ไม่เกิน US$0.25, idempotency/body conflict, cross-owner 404, CSRF, stale lease, crash หลัง dispatch/หลัง result commit ไม่ส่งซ้ำ, timeout/invalid citation ไม่สร้างคะแนน, exam admission บล็อก queued AI ก่อน dispatch และประวัติ
- Frontend: lint/build/TypeScript ผ่านใน isolated container; Node tests รวม asset guard **16 passed**; Playwright 10 specs **34 passed** แบบ route-mocked API รวม Tutor/drafts/error/auth/learning/exam-review และ 375/768/1440px
- Markdown links และ git diff --check ผ่าน ไม่รัน GitHub CI/ไม่ deploy ภายนอก/ไม่ commit-push ในรอบนี้
- Supabase migration wrapper ใช้ migration_owner อัปเดตใหม่เป็น `0023_dify_tutor` สำเร็จ; ตรวจ read-only แล้ว enabled=false, cost_bound_verified=false, daily_usd=0.250000, tutor_questions=0 ไม่สร้างคะแนนหรือคำตอบปลอม
- Local API ตอบ ready, Tutor availability แบบไม่มี session ตอบ 401; worker อ่าน secret ได้โดยพิมพ์เฉพาะ boolean ไม่แสดง key; ตรวจ worker/evaluator ผ่าน entrypoints ตามผลท้ายงาน
- UI จริงใน IAB ยังไม่มี session จึงยังไม่ตรวจ authenticated live UI/DB/Dify flow ด้วยบัญชีผู้ใช้จริง ไม่ใช้ mocked browser tests อ้างแทน
- Local images ใช้ cached API/runner เดิม + source app/migrations ล่าสุด ตรวจตรง source แล้ว ไม่อ้างว่าเป็น full public release build; PostgreSQL tmpfs/network ทดสอบถูกเก็บกวาดแยกจาก Supabase

ห้ามใช้ผลนี้อ้างว่า Dify semantic quality หรือ production acceptance ผ่านครบ

ดูขั้นตอนทดสอบด้วยมือทุกโมดูลใน [end-to-end-test-plan.md](end-to-end-test-plan.md)

## ตรวจหลังผู้ใช้ Publish outputs ใหม่ — 28 ต.ค. 2026

ผู้ใช้อนุญาตเรียกจริงหนึ่งครั้ง ใช้ `/workflows/run` เพื่อค้น version ที่ Publish ล่าสุด ไม่ retry และไม่เปลี่ยน runtime policy

- HTTP 200, status `succeeded`, ใช้เวลา 6,204 ms, reported `total_tokens=1215` (ไม่ใช่ยอดเงินจริง)
- Workflow `6f17038a-e2e1-45e4-9fce-fce38407041c`; run `a8a6daa1-a7a4-4442-838b-829ea2e7606a`
- Output มี `answer` และ `sources` แล้ว; sources 4 ชิ้น มี title/content/metadata.document_id
- Document ID `884d192c-2d99-4804-a080-c07b91df404c`; content ทั้ง 4 เป็นข้อความตรงตัวที่พบใน `knowledge/dify/soc-learning-guide-v1.md`
- คำถาม HTTP 403 ได้คำตอบว่าไม่ยืนยันการอ่าน/ขโมยข้อมูลสำเร็จ แนะนำตรวจ response/log เพิ่ม ไม่ประกาศคะแนนหรือ unlock; อ้าง `SOC-003` ซึ่งมีอยู่ใน retrieved snapshot จริง ไม่สร้าง `SOC-403`
- ตรวจ citation presence ผ่านสำหรับตัวอย่างนี้ แต่ chunks 3 ชิ้นไม่มีรหัสหัวข้อ และอีกชิ้นเป็นหัวข้อ SOC-003 อย่างเดียว ควรจัด chunk ให้เนื้อหาอยู่กับหัวข้อก่อนตรวจคุณภาพหลายคำถาม

นี่เป็น direct provider smoke test ไม่ใช่ authenticated web → API → DB/job → worker acceptance และไม่ใช่ semantic benchmark ไม่ได้เพิ่ม document/chunk hashes เป็น approved release ไม่ได้เปิด Tutor policy หรือยืนยัน per-call cost bound จาก token รวม การอนุมัติ corpus/config และการตรวจงบตาม gate ด้านบนยังคงค้าง

## ตรวจ Groq Workflow หลังผู้ใช้สั่งเชื่อม — 28 ต.ค. 2026

- เรียก `/workflows/run` จริงหนึ่งครั้ง ไม่ retry: HTTP 200, `succeeded`, Workflow `1169c8b9-b4ab-4ede-a535-3dfe2cca40f0`, run `9423b41a-0a32-4ac2-8d54-46097be3de89`, reported 1,630 tokens; ยอดนี้ไม่ใช่ค่าเงินจริงรวม
- ได้ answer และ sources 4 ชิ้น แต่ answer ยังมี leading `<think>` และไม่มี SOC section citation; ผลนี้ไม่ผ่านตัวตรวจ Tutor ปัจจุบัน ไม่ฝืนแสดงเป็นคำตอบที่รับรองแล้ว
- แก้ service ให้ตัดเฉพาะ complete leading reasoning block ก่อนตรวจ citation/บันทึกผล malformed/nested/embedded reasoning ถูกปฏิเสธ และ citation ที่อยู่เฉพาะใน reasoning ไม่นับ
- เพิ่มตรวจ `data.workflow_id` ให้ตรงกับ pinned request; version หาย/เปลี่ยนถูกปฏิเสธ ไม่รับ latest โดยเงียบ ๆ
- Ruff format/check ผ่าน; offline targeted tests `tests/test_dify_workflow.py tests/test_dify_client.py`: **25 passed** ไม่เรียก provider ใน tests และไม่ทดสอบ concurrency ใหม่ในรอบนี้
- Source/export ล่าสุดใช้ Groq LLM แต่ Weighted Score ยังอ้าง OpenAI embedding; ไม่ถือว่า Groq Free ครอบคลุมค่า retrieval ทั้งระบบ
- ยังไม่เปิด policy ไม่เปลี่ยน cost_bound_verified ไม่อ้าง authenticated web/worker flow ผ่าน และยังไม่ rebuild runtime images ด้วย patch รอบนี้

## ตรวจ Flow ที่แก้แล้วและข้อจำกัดแพ็กเกจ — 28 ต.ค. 2026 รอบบ่าย

- Actual Dify UI: คู่มือ AVAILABLE 21 chunks (intro + SOC-001..020), Full Text, ไม่มี rerank; แยก IF result not empty ไป LLM ส่วน no-match ไป constant template แล้วรวมผ่าน Variable Aggregator และ End เดียว ไม่มี tools/HTTP/SQL nodes ใน exported graph
- เก็บ export จริง `SOC (2).yml` เป็น `knowledge/dify/SOC-groq-import.yml` แทนไฟล์ร่างสอง End ที่มีชื่อ output ซ้ำ ไม่ใส่ credentials/environment variables
- ตรวจ Groq console พบ Free เป็น Current Plan; ไม่กด Upgrade โควตาโมเดล gpt-oss-20b ที่แสดง: 30 RPM / 1,000 RPD / 8,000 TPM / 200,000 TPD เป็นสถานะขณะตรวจ ไม่ใช่คำรับประกัน 200 prompts ต่อเนื่อง
- ตรวจ raw chunk ผ่าน Edit Chunk แล้ว Cancel (ไม่แก้เนื้อหา) ครบ 20 หัวข้อ เก็บ SHA-256 ใน `knowledge/dify/retrieval-review-20261028.json` เป็น candidate ยังไม่ activate policy และไม่อ้างว่าเป็น human review
- Published-latest smoke: HTTP 200, succeeded, workflow `99030ca5-fe8a-4b9e-a5ea-b1405053137f`, run `67db1f75-5ade-44b5-a4d8-3559e74a31cd`, 2,658 reported tokens; คำตอบ HTTP 403 อ้าง SOC-003/005 ที่อยู่ใน sources จริงทั้งคู่ ไม่มี reasoning tag; ไม่ใช่ benchmark หรือยอดเงินจริง
- พบโมเดลใช้ non-breaking hyphen `SOC‑003` แทน `SOC-003`: normalize เฉพาะรูป identifier ก่อนตรวจ citation ไม่เปลี่ยน source bytes/hash และยัง reject รหัสที่ไม่อยู่ใน snapshot
- no-match รับเฉพาะข้อความ constant ที่กำหนด + sources ว่าง และ worker ต้องเห็น total_tokens=0 จึงแสดง DIFY_NO_MATCH โดยไม่แสดงเป็น grounded answer; ข้อความไม่มีอ้างอิงแบบอื่นยัง reject
- **Blocker ที่ทดสอบจริง:** POST `/workflows/99030ca5-fe8a-4b9e-a5ea-b1405053137f/run` ได้ HTTP 403 `workflow_version_execution_not_allowed` แพ็กเกจ Sandbox ไม่อนุญาต execute version เฉพาะ ตรวจยืนยันจาก [Dify upstream service API](https://github.com/langgenius/dify/blob/main/api/controllers/service_api/app/workflow.py) ไม่ใช่ปัญหา key ผิด
- Transport คืน DIFY_PINNED_VERSION_UNAVAILABLE แบบชัดเจน ไม่ retry/fallback ไป latest โดยเงียบ ๆ เพราะไม่เท่ากับการล็อก execution version ตาม policy เดิม
- ยังไม่เปิด Tutor policy หรือเปลี่ยน cost attestation และยังไม่ rebuild backend runtime images รอบนี้ การใช้ published-latest + ตรวจ version หลังตอบกลับเป็นทางเลือกสำหรับ Free แต่ต้องตกลงความต่าง: ตรวจผลย้อนหลัง ไม่สามารถป้องกัน Flow ใหม่ถูกเรียกก่อนตรวจ version ได้ ห้ามอ้างว่าเทียบเท่า pinned execution
- ผลตรวจรอบบ่าย: Ruff format/check ผ่าน; offline `test_dify_workflow.py` + `test_dify_client.py` **29 passed** (pytest cache path read-only มี warning แต่ tests ผ่าน); typecheck ใน cached `soc-frontend-check:local` ไม่ผ่านเพราะ image ไม่มี dependencies @thesvg/react และ @supabase/ssr ตาม checkout ปัจจุบัน จึงยังไม่ถือว่า frontend ผ่านจาก image นี้; DSL ตรวจ End เดียว/answer+sources/no environment secrets ผ่าน; `git diff --check` ผ่าน ไม่ได้รัน DB concurrency, browser E2E หรือ GitHub CI ใหม่
- ตรวจซ้ำด้วย dependencies ที่ใช้งานจริงใน `soc-ui-demo`: `docker exec soc-ui-demo npm run typecheck` **ผ่าน** (exit 0) ไม่มีการติดตั้งหรืออัปเกรดแพ็กเกจเพื่อแก้ image เก่า

## เปิด Published-latest ตามคำอนุมัติผู้ใช้ — 28 ต.ค. 2026

- ผู้ใช้ตอบ “จัดการให้หน่อย” ต่อข้อเสนอ Published-latest พร้อม post-response version check จึงเปลี่ยน transport เป็น `/workflows/run` โดยยังตรวจ `data.workflow_id=99030ca5-fe8a-4b9e-a5ea-b1405053137f` ก่อนรับ outputs ไม่อ้างว่าเป็น pinned execution
- เพิ่ม circuit breaker อิง error ของ policy version นั้น: เมื่อพบ version mismatch, availability=false, POST ใหม่ 503 และ worker ไม่ dispatch งานใหม่จน operator re-approve; jobs ที่ส่งออกไปแล้วก่อนพบ mismatch ยังเป็นข้อจำกัดของ Published-latest
- ตรวจ raw intro เพิ่ม รวม hash release 21 chunks; manifest ระบุ Codex automated review ไม่อ้าง human review หรืออนุมัติข้อสอบ
- เพิ่ม one-shot `app.tutor.release` ใช้ migration_owner เท่านั้น, advisory lock, expected_version CAS, before/after audit transaction เดียว ไม่เพิ่ม/แก้ migration และไม่เปิดใน startup
- Activate Supabase local policy **version 2**, enabled=true, budget USD0.25/day UTC, call ceiling USD0.001 ภายใต้ Free/full-text/no-rerank; Runtime API/worker images `dify-free-20261028` อัปเดตแล้ว ไม่ deploy สาธารณะ ไม่เปลี่ยน investigation provider จาก mock และไม่แก้ evaluator grading
- คำขอที่ได้ completed response/version ตรงและมี token usage account เต็ม reserved ceiling เป็น reconciled ไม่ลดเป็น 0 ไม่ถือเป็น actual bill; timeout/version mismatch/unknown คง hold ข้ามวัน การเปลี่ยน credentials/plan/retrieval ต้องปิดและตรวจ cost ใหม่
- Regression tests กับ PostgreSQL ทิ้งได้ `soc_test_dify_free` และ runtime roles จริงผ่าน รวม >200 historic requests ไม่กลายเป็น lifetime cap, concurrent reservation, unknown holds, owner isolation, exam block, operator CAS/audit และ runtime privilege rejection
- Explicit live smoke `tests/test_tutor_live.py` ใช้ session สังเคราะห์ใน disposable local-auth DB และ **Dify จริง**: auth/CSRF → API → durable job → worker → provider → persisted result → owner GET ผ่านทั้ง HTTP403 grounded answer และ no-match 0-token branch; idempotent POST ไม่เพิ่ม logical request และอีกบัญชีอ่านไม่ได้ นี่ไม่ใช่ browser/Supabase OAuth acceptance หรือ held-out quality benchmark
- รวม targeted suite **39 passed**, Ruff ผ่าน, mypy 7 source files ผ่าน; frontend typecheck และ lint บน `soc-ui-demo` ผ่าน ไม่มี GitHub CI/production acceptance ในรอบนี้
- Browser guest UI ที่เปิดไว้ยังไม่มี session; ทดลองสมัครบัญชีสังเคราะห์ `@example.test` ถูก Auth ปฏิเสธก่อนเกิด session จึงไม่ถือว่าผ่าน Supabase signup จากการทดสอบนี้ การตรวจต่อ Google OAuth ถูก approval reviewer หยุดเพราะข้อมูลบัญชีบุคคลที่สาม ไม่อ่านข้อมูลหรือข้ามการปฏิเสธ ผู้ใช้ต้อง login เองหรืออนุญาตการตรวจ OAuth แยก
- ยืนยันหลังสลับ image รอบสุดท้าย: Supabase policy version=2, enabled/cost_bound_verified=true, workflow ตรง, reviewed_chunks=21; API/worker/evaluator healthy, worker credential readable โดยไม่แสดง key; เก็บกวาดเฉพาะ container/network PostgreSQL tmpfs ของงานนี้แล้ว ไม่ลบ Supabase หรือ volumes ผู้ใช้
