# ผลตรวจข้อ 14 — RAG และ Ask AI

ตรวจ local บน branch `codex/step-14-rag` ฐาน `7a5f142` (ข้อ 13); changes ข้อ 14 ยังไม่ commit และยังไม่ได้รัน GitHub CI ของ changes นี้ รายงานนี้ไม่ใช่หลักฐาน deploy หรือ production acceptance

## สถานะ

API/UI และ regression ที่ระบุด้านล่างผ่าน แต่ **ยังไม่ตรวจรับข้อ 14 ทั้งข้อ**: baseline เดิม Thai Recall@5=0.80 ยังคงเป็นผลไม่ผ่าน ส่วน release v2 ใช้ calibration ไทย/อังกฤษแยก แล้ววัด retrieval ใหม่ 50 ข้อได้ TH=0.95/EN=1.00 ด้วย developer labels จึงยังรอ independent relevance/grounding review, paired answer benchmark ของ release v2 และ unknown usage 6 calls ที่ต้อง reconcile จากข้อมูล provider จริง ไม่ปรับเกณฑ์หรือถือ failure เป็น success

## สิ่งที่เพิ่ม

- Authorized retrieval ด้วย pgvector แยก fake16/real768, release/config pin ต่อ run, frozen retrieval/citations และ retry snapshot เดิม ไม่รับ corpus หรือ source URL จาก client
- LangChain Core structured generation ผ่าน adapter เดิม, Pydantic/citation validation, แยก observation จาก guidance; คู่มืออย่างเดียวใช้ยืนยันเหตุการณ์ไม่ได้ ข้อมูล question/log/KB เป็น untrusted input และไม่มี tools/SQL execution
- Ticket questions API, triage RAG และ UI source drawer; loading, error, 409 draft, polling, no_match/unavailable/withdrawn และ mode ตรงจริง Source แสดง escaped text
- ตรวจ training identity ฝั่ง server; schema ปัจจุบันรับ training เท่านั้น ไม่มี exam endpoints ที่เปิด Ask AI ก่อน submit
- จอง query embedding/generation แยก component พร้อม shared rate/token/request caps; ไม่มี automatic retry ของ ambiguous provider call และ unknown usage ไม่ถูกนับเป็นศูนย์
- Revocation ตรวจ source/analysis/retry และ read projection ของ evaluation export โดยไม่เปลี่ยน immutable snapshot หรือคะแนน Instructor ใช้ assignment check เดิมร่วมกับการปิดบัง result
- Migration `0013`–`0017` เพิ่ม frozen RAG tables, dimension/profile/calibration, provider component ledger, revocation helpers และ composite FK ที่ผูก chunk/version/run/analysis; ไม่แก้ migration ที่ apply แล้ว

## ผลตรวจ local

| การตรวจ | ผล |
|---|---|
| Backend unit/contract (`pytest -m 'not integration'`) | 61 passed |
| PostgreSQL integration ทั้งชุด | 65 passed |
| PostgreSQL RAG/provider-budget หลังเพิ่ม reservation bounds, lease fencing และ HTTP revocation/replay checks | 11 passed ก่อนเพิ่ม review-only tests; full integration ล่าสุด 65 ผ่าน |
| Ruff check/format และ strict mypy จาก backend directory | ผ่าน |
| Approved OpenAPI validation, FastAPI contract drift และ generated TypeScript client | ผ่าน |
| Full disposable Compose CI | exit 0: PostgreSQL 65, HTTP smoke 3, Chromium 12 passed; preview-only 1 skipped ตาม environment |
| Frontend หลังปรับ source drawer ป้องกัน stale response | lint/build, asset guard และ targeted Assistant Playwright ผ่าน |
| Local Markdown links / git whitespace | ผ่าน |

Full Compose รอบล่าสุดใช้ project ทิ้งได้ `soc-ci-rag14-final` และ mock provider เท่านั้น; ตัว review tool/เอกสารที่เพิ่มภายหลังตรวจด้วย unit/static checks แยก ไม่ใช้การรัน provider จริงใน CI

Regression ครอบคลุม cross-run/event/knowledge citations, observation ที่ไม่มี event, prompt injection, no-match ไม่เรียก generation, retry frozen context, withdrawal/source 410/export และ immutable metrics, ownership/CAS/idempotency, finish/question race, non-training deny, unknown reconciliation, global budget เต็มไม่หยุด detector/tickets และ fake/real vector-space isolation

## Real Free Tier acceptance

ตัวเลขในส่วน baseline ด้านล่างเป็น checkpoint ก่อน calibration v2; ตัวเลขล่าสุดรวมทุกการเรียกอยู่ในส่วนการแก้เพิ่มและ ledger artifact ท้ายรายงาน

ได้รับอนุมัติ Gemini Free Tier ไม่มี billing, `gemini-embedding-2` 768 dimensions และ `gemini-3.5-flash-lite` เฉพาะข้อมูลจำลอง/คู่มือทั่วไป 2 เรื่องที่อนุมัติ งบเงินจริง 0 บาท; caps 100 dispatches/วัน UTC, 200,000 tokens/วัน และ 5 dispatches/60 วินาที ไม่มีการเปิด paid mode หรือ provider บน Render

[Benchmark artifact](artifacts/step-14-real-benchmark.json) เก็บคำถาม/ผล/สถานะ/model/call IDs และ configuration; [API smoke artifact](artifacts/step-14-real-api-smoke.json) เก็บ analysis/source และ export hash โดยไม่เก็บ session/key หรือ raw private evaluation

- Pilot 50 held-out questions: อังกฤษ 25, ไทย 25; RAG/no-RAG รวม 100 arm outcomes
- 95 outcomes succeeded (รวม 14 no-match templates ที่ไม่ dispatch generation), invalid output 4 และ provider failure 1 เก็บ `result=null` ตามจริง ไม่ retry แบบกลบ failure
- English RAG Recall@5 1.00, MRR 0.975; Thai Recall@5 0.80, MRR 0.775
- p50 generation/template latency ไม่รวม retrieval/embedding: EN no-RAG 2344 ms / RAG 2312 ms; TH no-RAG 7797 ms / RAG 4609 ms ไม่ใช้ตัวเลขนี้อ้าง end-to-end latency
- รวมการเตรียม corpus/calibration/smoke/benchmark/API acceptance: 98 tracked dispatches (document embedding 2, query embedding 5, generation 91), known usage 87,187 tokens และ unknown holds 47,207 tokens จาก 6 calls รวม 134,394 ภายในเพดาน 200,000 ไม่มีการ reset ledger เพื่อข้าม caps
- ค่าใช้จ่ายจริงที่ยืนยันครบยังเป็น `null` เพราะ unknown usage ไม่สรุปว่า provider รายงาน 0 บาทแม้เลือก project Free Tier/no billing
- Historical embedding calls 5 ครั้งยัง unknown เพราะ mapping เดิมไม่เก็บ `promptTokenCount`; mapping ใหม่ตรวจ real embedding ได้ 768 dimensions/3 tokens แต่ไม่ใช้ค่านั้นย้อนประมาณ usage เก่า อีก 1 call เป็น provider failure
- Current API smoke ใช้ FastAPI TestClient + session/CSRF + PostgreSQL + real worker/provider: question → matched structured answer → source → finish → frozen evaluation/export ผ่าน นี่ไม่ใช่การเดิน browser กับ Gemini end-to-end; browser tests ใช้ controlled API และ Compose integration แยกกัน

Benchmark ใช้ Question-v1 schema เดียวกันทั้งสอง arms ตลอดการ resume ไม่สลับ schema ตาม production metadata ที่เพิ่มภายหลัง; invalid output คงเป็น failure Label ของ pilot เป็น developer-authored ยังไม่ใช่ independent human review ไม่ปรับ threshold จาก held-out นี้แล้วนำผลเดิมมาอ้างใหม่

## วิธีเริ่มและงานค้าง

ดู [คู่มือ RAG](rag-development.md) สำหรับ mock local, operator ingestion/calibration/publish, flags และ reconciliation CLI ค่าเริ่มต้นปิด real calls และ CI ใช้ fake embeddings ไม่ index `docs/` ทั้งโฟลเดอร์

## การแก้เพิ่มตาม docs วันที่ 16 ต.ค. 2026

- Model tokenizer: preflight `countTokens` พร้อม system/schema ก่อน generation จริง; fail closed หากใช้ tokenizer ไม่ได้/เกิน 16k รวม output เผื่อ 1200 และตรวจ lease/revocation อีกครั้งก่อน chat ขนาด evidence/KB ยังคง byte cap ที่เข้มกว่า token cap เป็นด่านแรก
- แต่ละ count HTTP request อยู่ใน shared 100/day/5-per-minute cap, เก็บ counted input แยกจาก usage ที่ generation ใช้; ไม่มีการเอา counted tokens ไปคิดซ้ำ ตัว request admission เผื่อ embedding + count + chat 3 dispatches
- Numeric provider telemetry แยก input/output/thinking/latency และ retrieval SQL latency; ไม่บันทึก prompt/key/raw provider error
- Bilingual validation 8 queries แยกจาก held-out v1/v2 ทั้งหมด สร้าง release ใหม่ `a2808f51-f9fa-5fbe-8e91-441a4345980a` พร้อม threshold 0.4321524661316025 ไม่แก้ policy/run pins เก่า ดู [calibration](artifacts/step-14-real-calibration-v2.json)
- [Retrieval v2](artifacts/step-14-real-retrieval-v2.json): 50 คำถามใหม่, 20 answerable/5 unanswerable ต่อภาษา; EN Recall@5=1.00/MRR=0.975, TH Recall@5=0.95/MRR=0.95; unanswerable no-match 5/5 ทั้งสองภาษา ผลนี้ยังเป็น developer relevance labels ไม่ใช่ human-approved acceptance และไม่แทน baseline answer comparison
- [Real tokenizer smoke](artifacts/step-14-real-tokenizer-smoke.json): count 841 input tokens แล้ว generation succeeded; provider usage 1113 tokens; 2 dispatches นี่เป็น adapter smoke ไม่ใช่ browser/API acceptance รอบใหม่
- [Ledger/latency](artifacts/step-14-ledger-and-latency.json): รวม 109 dispatches ข้าม 2 วัน UTC (15 ต.ค. 95 /16 ต.ค. 14); known tokens รวม 89,213, unknown holds 47,207 จาก 6 calls ทุกวันยังต่ำกว่า caps เดิม; ไม่ reset ledger หรือส่ง ambiguous call ซ้ำ
- Retrieval SQL 25 samples/ภาษา: p50 rounded 0ms/p95 16ms (ความละเอียดเป็น ms), embedding batch 1985ms ร่วม 50 คำถาม ไม่ใช่ per-query end-to-end latency; tokenizer/generation smoke มีอย่างละ 1 sample ไม่อ้างว่าเป็น p95 ของระบบ
- เตรียม [คู่มือผู้ตรวจ](step-14-review-guide.md), review packets ที่ยังไม่มีคะแนนมนุษย์ และ offline scorer ซึ่งปฏิเสธ stale artifact, context/claim ที่แก้, cross-release refs, missing samples และไม่ตัด unsupported claims ออกจาก denominator

ต้องทำต่อก่อนตรวจรับคุณภาพ:

1. ผู้ตรวจอิสระยืนยัน relevant chunks ของชุด v2 และตรวจ supported claims ≥90% จาก evidence/context ที่แนบ ดูคู่มือ review; ไม่ให้ agent ที่เขียนงานลงคะแนนแทนมนุษย์
2. วัด full paired answer comparison บน release/config v2 หลังได้ labels ที่ผู้ตรวจยืนยัน; เก็บ baseline v1 ที่มี 4 invalid outputs/1 provider failure ไว้ ไม่ใช้ retrieval-only เป็นหลักฐานคุณภาพคำตอบ
3. Reconcile unknown usage ด้วยรายงาน provider ที่ยืนยันได้และ audit; เก็บ ledger ใน local container `soc-ci-rag14-real-db` ไม่ลบเพื่อเริ่มนับงบใหม่
4. Commit/review และยืนยัน GitHub CI ของ SHA ที่จะส่งจริง; ยังไม่มีการ push/PR/deploy ข้อ 14 จากงานนี้

ตรวจซ้ำจาก root: `backend/.venv/Scripts/python.exe scripts/check-doc-links.py` และ `git diff --check`; backend checks รันจาก `backend/` ตาม AGENTS เพื่อให้ strict config มีผล


## Agent self-review ที่ผู้ใช้อนุญาต

ตรวจเบื้องต้นครบแล้ว ดู [รายงานและข้อพบราย claim](step-14-agent-review.md): รองรับ 53/57 claims, ไม่ครบ 4; RAG EN 17/17 และกลุ่มคำถาม TH 18/19. Relevance v2 ยังคง TH Recall@5=0.95/EN=1.00 และมี Thai miss 1 ข้อ. ผลนี้เป็นการตรวจโดย agent ที่เขียน implementation เอง ไม่ใช่ human review; original human pending files, provider artifacts และสถานะตรวจรับข้อ 14 ยังคงเดิม. ไม่มี real API calls เพิ่มจากการ review นี้
