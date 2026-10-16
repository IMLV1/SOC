# Local RAG และ Ask AI — ข้อ 14

อ่าน [SRS](srs.md), [design](rag-langchain.md), [ผลตรวจ](step-14-verification.md)
และ [ฐานข้อมูล](local-development.md) ก่อนเปิด feature. ไม่รัน provider จาก API startup/migration.

## เริ่มแบบ offline

ใช้ Compose/secrets จากคู่มือเดิม (`scripts/init-local.py` เมื่อยังไม่มีเท่านั้น),
รัน migration wrapper ผ่าน `docker compose up -d --build` ตาม environment ของตน.
อย่าล้าง volumes ของระบบที่มีข้อมูลเพื่อเริ่มใหม่.

ใช้ seed image เป็น operator one-shot (ใน Bash จาก repository root):

```bash
docker compose run --rm --entrypoint python seed -m app.knowledge admit /app/knowledge/manifest.json
# จด release UUID ที่คืนมา; รอ worker ingest สอง jobs ให้เสร็จ
# ไฟล์ golden เป็น test/operator asset ที่ mount เพิ่ม ไม่อยู่ใน knowledge manifest
docker compose run --rm --entrypoint python   -v "$PWD/backend/tests/knowledge_queries.json:/golden.json:ro" seed   -m app.knowledge validate RELEASE_UUID /golden.json
docker compose run --rm --entrypoint python seed   -m app.knowledge publish RELEASE_UUID --expected-version ACTIVE_VERSION
```

`ACTIVE_VERSION` เริ่ม 1 เฉพาะฐานใหม่; อ่าน version จริงจาก `kb.active_release` ด้วย publisher connection
ก่อน publish ครั้งถัดไป. Partial/revoked corpus หรือ golden fail ต้องแก้ให้ถูกก่อน publish.
ตั้ง `SOC_KB_ENABLED=true`, `SOC_AI_PROVIDER=mock` แล้ว recreate API/worker ด้วย Compose.
Run ใหม่จึง pin release; ไม่เติม RAG ย้อนหลังให้ run เก่า. เข้าสู่ระบบ → สร้าง run → ticket → Ask AI.
หน้ารอบฝึกยังแสดง triage และลิงก์ investigation; source drawer อยู่หน้า ticket.

รอบที่สร้างตอน RAG disabled ถามไม่ได้ (503); run อ่านอย่างเดียวหรือ ticket deleted ถามไม่ได้ (409).
คำถาม 1–2,000 chars + expected ticket version, CSRF และ Idempotency-Key.
409/เครือข่ายขาดไม่ล้าง draft; pending poll มี backoff และพักเมื่อแท็บซ่อน.

## Gemini ที่อนุมัติแล้ว เฉพาะ local

ผู้ใช้ยืนยัน Gemini Free Tier **ไม่มี billing**, `gemini-embedding-2` / 768 dimensions,
`gemini-3.5-flash-lite`, corpus คู่มือ authentication/blocked สองเรื่องเดิม และงบ 0 บาท.
คง caps 100 dispatches/200,000 tokens ต่อ UTC day, 5 dispatches/60 วินาที,
20 logical requests ต่อ user/day. แยก embedding/generation และ unknown holds.

Key อยู่ไฟล์ส่วนตัว `.local/secrets/gemini_api_key.txt` หรือ path เดิมที่เก็บไว้;
ใช้ `GEMINI_API_KEY_FILE` ฝั่ง worker/operator เท่านั้น ไม่ส่งลง browser/NEXT_PUBLIC/log.
เปิดเฉพาะ environment ที่อนุมัติ:

```text
SOC_AI_PROVIDER=gemini_free
GEMINI_PROJECT_TIER_CONFIRMED=free_no_billing
GEMINI_SYNTHETIC_DATA_ONLY=true
GEMINI_CHAT_MODEL=gemini-3.5-flash-lite
SOC_RAG_REAL_CONFIRMED=approved-corpus-free-v1
SOC_KB_ENABLED=true
```

ต้องสร้าง real release แยกจาก fake release ก่อน: operator `python -m app.knowledge prepare-real FAKE_RELEASE_UUID`
จะอ้าง reviewed immutable chunks เดิมแล้ว enqueue real ingestion jobs. Worker ที่มี key จึงสร้าง vectors 768;
ไม่มี vector-space mixing หรือ auto-call จาก CI. ยังไม่ publish จน embedding ครบและ calibration ผ่าน.

Operator `python -m app.knowledge calibrate-real REAL_RELEASE_UUID /path/to/calibration.json --nonce UNIQUE_OPERATOR_NONCE`
ใช้ owner connection สำหรับ publish rights และ `KNOWLEDGE_WORKER_PASSWORD_FILE` สำหรับ worker connection
ในการจอง provider calls. ต้อง mount credentials ทั้งสองให้ one-shot operator อย่างชัดเจน;
ไม่ให้ API ถือ owner credential. Calibration JSON ใช้ profile `gemini-embedding-2-768-v1`
และ `calibration` 4–8 cases `{query, expected}` (อย่างน้อยสอง positive stable keys และสอง null/no-match),
แยกจาก held-out set. ตรวจ free-tier approval ก่อนคำสั่งนี้เพราะมี real calls.
หาก rate/budget ไม่พอ คำสั่ง fail closed; nonce ใหม่เป็น operator ยืนยัน logical calls ใหม่ ไม่ใช่ exactly-once replay.
หลังผ่านจึง `publish` ด้วย expected active version แล้วสร้าง run ใหม่.

## การตรวจและ benchmark

CI: backend unit/contract + PostgreSQL integration และ Playwright จาก `scripts/ci-compose.sh`
ใช้ mock เสมอ; regression ใหม่รวมใน test discovery เดิม ไม่เพิ่ม paid CI job.

Manual benchmark อยู่ `backend/tests/rag_benchmark.py` และต้องใช้ฐานทิ้งได้ชื่อ
`soc_test_rag14_real`, role secret files, loopback PostgreSQL port และ opt-in Gemini ด้านบน.
ตัว script ไม่ลบฐานเดิม ใช้ migration wrapper/checksum และบันทึก checkpoint ใน `.local/`.
เริ่ม `--max-calls 12` สำหรับ smoke แล้ว `--full --max-calls 100` ภายใต้ shared global caps.
ไม่เปลี่ยน key/model/corpus หรือ reset usage ledger เพื่อข้ามเพดาน.
เก็บ invalid_output เป็น failure/result=null, ไม่เผย raw model output;
provider outage หยุด dispatch จน operator ตรวจ ไม่ retry ambiguous call อัตโนมัติ.
No-match เป็น template ไม่มี generation call แม้ mode ของ analysis เป็น real.

ผล pilot ครั้งนี้และ call IDs อยู่ใน [artifact](artifacts/step-14-real-benchmark.json).
Thai Recall@5 ยังต่ำกว่า target; อย่าปรับ threshold จาก held-out ชุดนี้แล้วอ้างว่าเป็น held-out เดิม.
ต้องใช้ validation ใหม่และ independent held-out/reviewer ก่อนรับรองคุณภาพ.
หก unknown usage holds ยังต้อง reconcile ด้วยรายงาน provider จริง ไม่ใช้ค่าประมาณหรือ 0.
ฐาน local สำหรับหลักฐานชื่อ container `soc-ci-rag14-real-db`; เก็บ ledger ไว้เพื่อ reconcile.
การ reconcile analysis ใช้ CLI เดิมเพิ่ม `--component query_embedding|generation`;
operator/ingestion call ใช้ `python -m app.analysis.reconcile --operation OPERATION_KEY --tokens CONFIRMED_TOKENS --reason REPORT_REFERENCE`
ด้วย owner credential เท่านั้น มี audit และปฏิเสธค่าที่ไม่ยืนยัน/การ reconcile ซ้ำ. ห้ามใช้ estimated tokens จากการเรียกใหม่แทนรายงานจริง.

## ข้อจำกัด

ยังไม่เปิด exam/learning endpoints, ไม่มี paid mode/production approval, ไม่มี provider streaming/tools.
การเปลี่ยน profile/dimension ใช้ migration/table ใหม่; ไม่ drop fake profile หรือเปลี่ยน pin ของ run เดิม.
Revoke version ด้วย publisher CLI ทำให้ read/retry ปฏิเสธหรือ withdrawn ตาม contractทันที;
ไม่แทนด้วย active release ใหม่และไม่แก้คะแนน snapshot.
Render auth-only preview ไม่มี background runner และไม่ได้เปิด RAG จากงานนี้.


## Token preflight และ validation รุ่นใหม่

Migration `0017_provider_telemetry` เพิ่ม provider `token_count` กับ numeric telemetry และ retrieval latency.
Generation จริงเรียก Gemini `countTokens` ด้วย GenerateContentRequest (รวม system/schema)
ก่อน chat; ถ้า count ล้ม/เกิน conservative 16k window รวม output 1200 จะ fail closed.
นับ countTokens ใน global 100/day และ 5/min เช่นกัน; token length ที่นับได้ไม่ใช่ tokens ที่ generation ใช้.
Network ที่ไม่ทราบผลยังถือ unknown hold ไม่มี fallback เงียบเป็น byte estimate.
ขนาด event/KB ยังจำกัดด้วย bytes ที่เข้มกว่าข้อเสนอ token caps และมี exact full-request preflight ซ้ำ.
ดู [Google token counting](https://ai.google.dev/api/tokens).
Worker ตรวจ lease/revocation อีกครั้งหลัง count ก่อน generation; network ทั้งสองครั้งอยู่นอก domain transaction.

CLI `prepare-real SOURCE_RELEASE --calibration-id UNIQUE_ID` สร้าง release ใหม่สำหรับ threshold ใหม่
โดย reuse reviewed immutable chunks/vectors; ไม่ update policy/run pin เก่า.
Calibration operator รอ rate window โดยไม่มี transaction ค้าง; preflight ปฏิเสธ policy ที่ freeze แล้วก่อน dispatch.
`backend/tests/knowledge_calibration_v2.json` มี 8 validation cases แยกจาก held-out v1/v2.

Manual retrieval runner จาก backend: `python -m tests.rag_retrieval_benchmark --release RELEASE_UUID --suite tests/knowledge_heldout_v2.json --secrets ../.local/secrets --operation UNIQUE_OPERATION --output ../.local/retrieval-result.json`.
ต้องตั้ง opt-ins เดิม ใช้ฐานทิ้งได้ `soc_test_rag14_real`; หนึ่ง embedding batch เก็บทั้ง failure และ usage,
ไม่ reset DB, ไม่ overwrite report หรือส่ง ambiguous operation เดิมซ้ำ. ตัวนี้วัด retrieval เท่านั้น.

ผล real v2 แยกจาก baseline เดิม ดู [retrieval artifact](artifacts/step-14-real-retrieval-v2.json)
และ [tokenizer smoke](artifacts/step-14-real-tokenizer-smoke.json).
ก่อนรับรองคุณภาพต้องทำ [human review](step-14-review-guide.md); ไม่มี automatic human scores.
