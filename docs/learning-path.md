# Learning path และการทดสอบเลื่อนระดับ (ข้อกำหนด)

เอกสารนี้เพิ่มเป้าหมาย **สอนคนที่ยังไม่เก่ง Cybersecurity ให้ตรวจหลักฐาน SOC ได้ทีละขั้น** ลงในขอบเขตของ [SOC simulation](soc-simulation.md) ไม่แทนที่ detection, ticket หรือการทดลอง A/B/C เดิม สถานะปัจจุบัน: [HTML prototype](../prototype/README.md) สาธิต flow ได้ backend/ฐานข้อมูล/auth มี foundation แล้ว; AI+RAG และข้อสอบจริงยังไม่เปิด

## ลำดับผู้เรียน

| ระดับ | บทเรียนก่อนสอบ | เคสทดสอบใน prototype | เกณฑ์เปิดระดับถัดไป |
|---|---|---|---|
| เริ่มต้น | อ่าน HTTP Method, Path, Response, บัญชี/IP และแยกความพยายามจากผลกระทบ | S01, S03 | จบบทเรียนและผ่านทั้ง 2 เคส |
| กลาง | เชื่อม request หลายรายการ ตรวจ session, ข้อมูลที่เข้าถึง และ change ticket | S04, S02 | จบบทเรียนและผ่านทั้ง 2 เคส |
| ชำนาญ | เทียบ baseline กับพฤติกรรมจริง หาหลักฐานอิสระก่อนสรุป anomaly | S05 | จบบทเรียนและผ่านเคส |

ผู้สมัครใหม่เริ่มที่ระดับเริ่มต้นและเห็น onboarding อธิบายปุ่ม/หน้าต่าง ๆ Guest ดูเส้นทางและ demo แบบอ่านอย่างเดียวได้ เมื่อเปิดระดับใหม่ต้องแสดงคำแนะนำระดับนั้นและให้ทำบทเรียนก่อนเริ่มข้อสอบ ผู้เรียนกลับไปทบทวนบทเรียนเก่าได้โดยไม่ลบผลสอบ

**ข้อสรุปผู้ใช้ 17 ต.ค. 2026:** ต้อง login ก่อนอ่านเนื้อหาบทเรียน แม้ข้อกำหนดเดิมระบุ Guest ทบทวนบทเรียนได้ ดังนั้น Guest อ่านได้เฉพาะ metadata เส้นทางและ demo; `GET /lessons/{lesson_id}` ต้องมี session การตัดสินนี้มีผลเหนือข้อความ Guest ในเอกสารเดิม

### ช่วงเรียน

1. แสดง **ตัวอย่างฝึกที่ระบุว่าเป็นตัวอย่าง** ไม่ใช้โจทย์สอบ/เฉลยจริง บอกว่าจะดู request ที่ไหนและกดจุดใด
2. พาอ่าน Method + Path → Response status → บัญชี/Source IP → timeline/context พร้อมตัวอย่างข้อความ request/response และความหมายของ 200, 401, 403 ที่ไม่เหมารวมว่า `200` คือภัย หรือ `401/403` คือปลอดภัยทั้งเคส
3. ผู้เรียนกด field ที่กำลังสอนก่อนเปิดคำอธิบายและขยับขั้น บทเรียนต้องอธิบายด้วยว่า *ข้อมูลนี้ยังพิสูจน์อะไรไม่ได้* และทำไมต้องดู event อื่น
4. บันทึก `lesson_completed` ต่อผู้ใช้และเวอร์ชันบทเรียน ฝั่ง server ในระบบจริง ไม่ถือว่าการกดข้ามขั้นหรือการอ่านอย่างเดียวคือผ่านข้อสอบ

### ช่วงทดสอบเลื่อนระดับ

1. Server ตรวจว่าผู้ใช้ผ่านบทเรียนของระดับนั้นและระดับก่อนหน้าแล้ว ก่อนสร้าง exam attempt ไม่ใช่ตรวจแค่ปุ่มถูกปิด
2. แสดงเฉพาะเหตุการณ์ที่ปล่อยแล้ว รวม request, response, log, alert และ ticket ชื่อเคส/ความรุนแรงตั้งต้นเป็นกลาง ไม่แสดง mock AI brief, คู่มือ, rubric, label หรือเฉลยระหว่างสอบ
3. ผู้เรียนเลือก event ที่ใช้ชี้ขาด ระบุ severity, disposition และเหตุผลที่อ้างผลกระทบจริงกับสิ่งที่ยังไม่ทราบ ระบบรับคำตอบสุดท้ายแล้ว freeze attempt จึงประเมิน
4. ตรวจหลักฐานครบและ ID อ้างอิงด้วยกฎฝั่ง server; AI+RAG ช่วยประเมิน **คุณภาพเหตุผล** โดยค้นคู่มือที่อนุมัติแล้วและอ้าง citation แยกจาก event evidence ไม่ให้ LLM เปลี่ยน ground truth หรือปลดล็อกเอง
5. ถ้าผ่านทุกเคสของระดับ ให้เปิดระดับถัดไปแบบ atomic พร้อมแจ้งบทเรียนใหม่ ถ้าไม่ผ่าน แสดง feedback หลังส่งเท่านั้นและให้เริ่ม attempt ใหม่ตามโควตา Instructor ตรวจผล/override ได้พร้อมเหตุผลและ audit; คำตอบที่มีความกำกวม, AI ล่ม หรือ citation ไม่ถูกต้องให้สถานะ `needs_review` ไม่ตัดสินผ่านอัตโนมัติ

คำว่า **ผ่าน** ในระบบจริงต้องมี rubric ที่ versioned และกำหนดก่อนสอบ เช่น ความครบของหลักฐาน, ข้อสรุป, severity และเหตุผลที่เชื่อมหลักฐาน แต่ละข้อมีคะแนน/เกณฑ์และผลตรวจแยกกัน ไม่ใช้ความยาวข้อความอย่างเดียวแทนความถูกต้อง คะแนน/feedback ต้องระบุเวอร์ชัน rubric, AI model, knowledge release และ evidence snapshot ที่ใช้ เพื่อให้ทบทวนย้อนหลังได้ ผล AI เป็นคำแนะนำที่ตรวจสอบได้ ไม่ใช่ผู้ตัดสินเพียงแหล่งเดียว

## Functional requirements เพิ่มเติม

| ID | ข้อกำหนด | ตรวจรับ |
|---|---|---|
| LEARN-01 | หลัง login ครั้งแรกแสดง onboarding และเส้นทางระดับ พร้อมปุ่มเปิดคำสอนซ้ำ | ผู้ใช้ใหม่บอกทางไป Event/Ticket/Submit ได้จาก UI |
| LEARN-02 | บทเรียนสอน request/response ทีละจุดและบันทึกความคืบหน้า | ปิด/เปิดหน้าแล้วกลับไปเรียนต่อได้โดยไม่เสียความคืบหน้า |
| LEARN-03 | Gate บทเรียน/ข้อสอบ/ระดับถัดไปฝั่ง server | เรียก API ตรงหรือแก้ client state แล้วข้ามระดับไม่ได้ |
| LEARN-04 | Exam ซ่อนคำใบ้ เฉลย และ initial severity พร้อมแยกชุดฝึกกับชุดสอบ | response ทุก endpoint ก่อนส่งไม่มี private label/answer; demo ไม่ใช้ fixture ข้อสอบเดียวกัน |
| LEARN-05 | บันทึกคำตอบและ evidence refs แบบ immutable หลัง submit | submit ซ้ำด้วย idempotency key ไม่สร้างผลสองครั้ง; ส่งก่อน evidence ครบได้ validation error |
| LEARN-06 | ประเมินด้วย deterministic checks + AI/RAG explanation ที่อ้างหลักฐาน/คู่มือถูกชุด | ข้อความเหตุผลสั้นแต่ถูกไม่ถูกตัดทิ้งเพราะความยาว; อ้าง event ที่ไม่อยู่ใน snapshot ไม่ผ่าน |
| LEARN-07 | แสดง feedback หลังสอบ รองรับ retake และ Instructor review/override | ผลที่แก้มีผู้อนุมัติ เหตุผล เวลา และ audit; ระดับที่ปลดล็อกไม่เปลี่ยนเงียบ ๆ |

## Non-functional และความปลอดภัย

- Responsive และเข้าถึงด้วยคีย์บอร์ดได้ ทั้งปุ่มตัวอย่างและแบบฟอร์มต้องมี label/focus state; สีไม่ใช่สัญญาณผ่าน/ไม่ผ่านเพียงอย่างเดียว
- แยก `training` corpus/fixture จาก `exam` bank และ private answer key โดย server-only storage/role; ไม่ส่งเฉลยใน JavaScript bundle, catalog, prompt retrieval, log หรือ API ก่อน submit
- ตรวจ owner, role, quota และ rate limit ทุก mutation; เก็บข้อมูลผู้เรียนและ AI usage ตาม retention policy พร้อม redaction ของ request/log ที่อาจมี credential
- เก็บคะแนนและการปลดล็อกแบบ transaction เดียว ป้องกัน submit ซ้ำ/concurrent tabs; AI failure ไม่ต้องทำให้คำตอบหายหรือให้คะแนนผ่านโดยเดา
- วัด completion rate, pass/retake rate, rubric disagreement และการทบทวนโดย Instructor แยกจาก precision/recall ของ detector; ห้ามใช้ผลสอบผู้เรียนเป็นหลักฐานว่า AI ตรวจภัยแม่นขึ้น

## ข้อมูลขั้นต่ำและความสัมพันธ์

`users 1—N lesson_progress`, `learning_levels 1—N lessons`, `learning_levels 1—N exam_cases`,
`users 1—N exam_attempts`, `exam_attempts 1—0..1 exam_answers` (หนึ่ง frozen answer ต่อเคส/attempt),
`exam_attempts 1—N grading_revisions`, `grading_revisions 1—N grading_citations` และ
`users 1—N level_unlocks` โดย attempt ผูกกับ run_id, scenario_version, rubric_version,
evidence_snapshot_hash และผู้เรียน Retake สร้าง attempt ใหม่ ไม่เพิ่ม final answer ใน attempt เดิม
ดู [Database](database.md), [API](api.md) และ [SRS](srs.md)

Policy ที่ผู้ใช้ยืนยัน 13 ต.ค. 2026: Instructor ดูเฉลยสอบได้หลัง submit เท่านั้น;
ผู้เรียนได้รับเฉพาะ feedback ตาม rubric ไม่เปิดเฉลยเต็มแม้สอบจบแล้ว
ค่าเริ่มต้น rubric/retake/override กำหนดไว้ใน SRS §8 ตามที่ผู้ใช้มอบหมาย 17 ต.ค. 2026; backend grading primitives เริ่มต้นใน `backend/app/grading/rubric.py`. Exam/review/unlock API ยังไม่ implement.

## ขอบเขตของ prototype ปัจจุบัน

`prototype/` ใช้ localStorage เก็บบทเรียนที่เรียนจบและผลเคสต่อบัญชีเดโม แสดงตัวอย่าง request แบบกด 5 จุด ซ่อน AI brief/ชื่อที่ใบ้ผล/initial severity ในรอบสอบ และให้ rubric จำลอง 4 ข้อหลังส่ง ผลลัพธ์นี้ **ไม่ใช่ AI+RAG จริง** และไม่ได้พิสูจน์ว่าผู้เรียนเข้าใจข้อความอิสระ เพราะตรวจเหตุผลด้วยความยาวขั้นต่ำเท่านั้น Fixture/เฉลยและ demo ยังอยู่ใน browser/ชุดเดียวกัน จึงใช้สอบแบบป้องกันการดูเฉลยไม่ได้ ต้องทำ LEARN-03–07 ฝั่ง backend ก่อน deploy เป็นข้อสอบจริง
