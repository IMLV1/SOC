# วิธีตรวจคุณภาพข้อ 14 สำหรับผู้ตรวจ

ไม่ต้องเขียนโค้ดหรือมี API key และการตรวจนี้ไม่เรียก Gemini เพิ่ม ผู้ตรวจควรเป็นคนที่ไม่ได้เขียน implementation หรือกำหนดคำตอบอ้างอิงเอง เช่น เจ้าของงาน ผู้สอน หรือเพื่อนร่วมทีม ตัวเลขจากการรันเครื่องและการตรวจความหมายของคำตอบเป็นหลักฐานคนละส่วน

## ต้องตรวจอะไร

| งาน | สิ่งที่ดู | เกณฑ์ |
|---|---|---|
| Retrieval relevance | คู่มือส่วนใดช่วยตอบคำถามได้จริง | Recall@5 ≥0.85 แยกไทย/อังกฤษ หลังคนยืนยัน relevant chunks |
| Answer grounding | ทุก claim ที่สุ่มมาตรงกับ event หรือคู่มือที่อ้างหรือไม่ | Supported claims ≥90%; รายงานแยกไทย/อังกฤษและ RAG/no-RAG |
| ข้อห้าม | คู่มือถูกใช้ยืนยันเหตุการณ์, ข้อมูลนอกหลักฐาน, หรือกล่าวว่า 403 พิสูจน์ compromise | ให้ไม่รองรับ พร้อมเหตุผล ไม่เปลี่ยน label เพื่อให้คะแนนผ่าน |

ระบบตรวจ citation UUID/FK/ownership อัตโนมัติได้ แต่ citation ที่มีอยู่จริงอาจไม่ได้รองรับข้อความนั้น เช่น event แสดง HTTP 403 และ request_policy_denied จึงรองรับว่า request ถูกปฏิเสธ แต่ไม่รองรับว่าอ่านข้อมูลสำคัญสำเร็จ ส่วนคู่มืออธิบายหลักการ ไม่ใช่หลักฐานว่าเหตุการณ์เกิดขึ้นจริง

## ชุด A: retrieval ใหม่

เปิด [retrieval review draft](artifacts/step-14-retrieval-review.pending.json) มีคำถาม 50 ข้อ (ไทย 25 / อังกฤษ 25) กับ approved chunks 2 ส่วนใน `sources` ใช้ผลจริงจาก [retrieval v2](artifacts/step-14-real-retrieval-v2.json)

อ่านคู่มือใน `sources` แล้วกรอกแต่ละรายการใน `labels`:

- `relevant_chunk_ids`: ID ของ chunk ที่เกี่ยวข้องจริง คัดจาก `sources[].chunk_id`; ถ้าไม่มีใช้ `[]` ไม่เพิ่มแหล่งอื่นนอก corpus
- `answerable`: `true` หาก approved corpus ช่วยตอบได้, `false` หากไม่มีแหล่งที่เกี่ยวข้อง ไม่ใช่ถามว่าโมเดลมีความรู้ทั่วไปหรือไม่
- `expected_evidence_ids`: หลักฐาน event ที่ต้องมีเพื่อสรุปข้อเท็จจริง คำถามคู่มือทั่วไปใช้ `[]` ได้; retrieval-only ชุดนี้ไม่ได้ยืนยันเหตุการณ์ของผู้เรียน
- `forbidden_claims`: ข้อสรุปที่ห้ามอ้างจากบริบทนี้ เช่น “พิสูจน์ว่าข้อมูลถูกขโมยแล้ว”
- `reason`: เหตุผลสั้น ๆ ว่าคู่มือรองรับเรื่องใดหรือเพราะอะไรจึงไม่มีคำตอบ
- `approved`: เปลี่ยนเป็น `true` หลังตรวจจริงเท่านั้น

กรอก `reviewer` เป็นชื่อหรือรหัสของผู้ตรวจจริง และ `independent_of_implementation=true` เมื่อผู้ตรวจไม่ได้เขียน implementation/labels เอง ช่องนี้เป็นคำรับรองของผู้ตรวจ ไม่ใช่การยืนยันตัวบุคคลจากระบบภายนอก

อย่าแก้ `artifact_sha256`, `sources`, `id`, `language`, `query` หรือรายการที่สุ่มมา ตัวตรวจปฏิเสธ context ที่ถูกเปลี่ยน/ID นอก release และรายการที่หายไป

## ชุด B: claims ของ baseline ที่รันจริง

เปิด [human review draft](artifacts/step-14-human-review.pending.json) มี 57 claims จากคำตอบ 40 รายการ (สุ่มคงที่ 10 คำตอบต่อภาษา/arm จากคำตอบที่มี claims) พร้อม `sources` และ `evidence_context` ซึ่งเป็น synthetic event ตัวเดียวกับ benchmark เดิม

แต่ละ `claims` มีข้อความ, `evidence_refs`, `knowledge_refs`, language และ arm:

1. เทียบ `evidence_refs` กับ `evidence_context` และ `knowledge_refs` กับ `sources`
2. กรอก `supported=true` เมื่อแหล่งที่อ้างรองรับข้อความทั้งหมด; ถ้าบางส่วนเกินหลักฐานให้ `false`
3. กรอก `reason` อธิบายสั้น ๆ เช่น “event ยืนยันแค่ปฏิเสธคำขอ ไม่พบหลักฐานอ่านข้อมูลสำเร็จ”
4. ถ้ายังตัดสินไม่ได้ ให้คง `null` และเขียนเหตุผล จะยังเป็น pending ไม่ถูกนับเป็นผ่าน

`labels` ในไฟล์นี้เป็นคำถาม baseline เดิมอีก 50 ข้อ ใช้ตรวจ relevance ของ baseline แยกจากชุด A; `relevant_source_ids` เป็น frozen retrieval item IDs ของ pilot เดิม ไม่ใช่ chunk UUID ของชุด A ห้ามคัด ID ข้ามชุด

ผล baseline เดิม Thai Recall@5=0.80 และมี invalid outputs/provider failure อยู่จริง แม้กรอก review ครบก็อาจได้สถานะ failed เพราะผล baseline ยังต่ำกว่าเกณฑ์ ต้องเก็บผลนั้นไว้ การประเมิน retrieval v2 ที่ดีขึ้นไม่ใช่การเปลี่ยนผล baseline ให้ผ่าน และยังไม่ใช่ full paired answer benchmark ของ release v2

## วิธีตรวจไฟล์ด้วยโปรแกรม

จาก `backend/` หลังติดตั้ง dependencies ตาม [คู่มือเริ่ม RAG](rag-development.md):

```bash
python -m app.knowledge.review assess-retrieval ../docs/artifacts/step-14-real-retrieval-v2.json ../docs/artifacts/step-14-retrieval-review.pending.json
python -m app.knowledge.review assess ../docs/artifacts/step-14-real-benchmark.json ../docs/artifacts/step-14-human-review.pending.json
```

Exit 2 = ยังตรวจไม่ครบ, exit 1 = ตรวจครบแต่ต่ำกว่าเกณฑ์, exit 0 = ผ่านเฉพาะมิติที่คำสั่งนั้นตรวจ ไม่เท่ากับครบข้อ 14/CI/deployment ผลทุกครั้งผูกกับ hash ของ artifact เดิม

หลัง review ให้แจ้งว่าตรวจไฟล์แล้ว ไม่ส่ง API key/secret ใด ๆ ขั้นถัดไปคือดูว่าจุดใดต้องแก้ แล้ววัด paired answer benchmark บน release/config ใหม่โดยใช้ held-out ที่ผู้ตรวจยืนยัน ภายใต้ global caps เดิม ไม่ใช้ผลชุดที่ปรับ threshold มาแทน held-out

## ตัวเลขล่าสุดและสิ่งที่ยังค้าง

Calibration v2 ใช้ 8 คำถามแยกจาก held-out ใหม่ทั้งหมด โดยเก็บ threshold ใน release ใหม่ ไม่เปลี่ยน pin ของ run เก่า ผล developer labels ของ retrieval v2: EN Recall@5=1.00/MRR=0.975, TH Recall@5=0.95/MRR=0.95; no-match ของคำถามนอกขอบเขต 5/5 ทั้งสองภาษา ยังต้องให้คนยืนยัน relevance ก่อนรับรองผล

ยังไม่มีคนกรอกคะแนน review, ไม่มี full paired answer benchmark ของ release v2, unknown usage เดิม 6 calls ยังไม่ reconcile และ GitHub CI ของ changes นี้ยังไม่รัน จึงยังไม่ติ๊กข้อ 14 ทั้งข้อ ดู [รายงาน](step-14-verification.md) สำหรับ checks/หลักฐานและข้อจำกัด


## Agent self-review ที่ผู้ใช้อนุญาต

ตรวจเบื้องต้นครบแล้ว ดู [รายงานและข้อพบราย claim](step-14-agent-review.md): รองรับ 53/57 claims, ไม่ครบ 4; RAG EN 17/17 และกลุ่มคำถาม TH 18/19. Relevance v2 ยังคง TH Recall@5=0.95/EN=1.00 และมี Thai miss 1 ข้อ. ผลนี้เป็นการตรวจโดย agent ที่เขียน implementation เอง ไม่ใช่ human review; original human pending files, provider artifacts และสถานะตรวจรับข้อ 14 ยังคงเดิม. ไม่มี real API calls เพิ่มจากการ review นี้
