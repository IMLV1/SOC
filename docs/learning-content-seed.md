# เนื้อหาฝึก JSON — 3 ระดับสำหรับเตรียมทดสอบ

เพิ่มวันที่ 21 ต.ค. 2026 ตามคำขอให้เตรียมเป็น **ไฟล์ JSON เท่านั้น ไม่แตะ PostgreSQL ในเครื่อง**

ต้นฉบับ: [curriculum-v1.json](../backend/fixtures/learning/curriculum-v1.json)

หน้าอ่านตัวอย่าง: `/demo/learning` และหน้าฝึกรวม `/demo/learning?view=practice`
อ่านสำเนา training ที่ export แบบ allowlist รายไฟล์ไว้ใน
[`frontend/public/learning/`](../frontend/public/learning/)
ไม่ import โฟลเดอร์ backend เข้า frontend และไม่ใช้ exam fixtures

สถานะ `draft_for_testing`, `purpose=training` มี 3 ระดับ / 9 บทเรียน / 45 ขั้น
แต่ละขั้นมีจุดให้กดดู (`target`), คำอธิบาย (`explanation`) และข้อจำกัดที่ยังสรุปไม่ได้ (`limitation`)
ตัวอย่างทุกชุดเป็นข้อมูลฝึก ไม่ใช่โจทย์สอบหรือเฉลยจาก exam bank

## เนื้อหา

| ระดับ | บทเรียน |
|---|---|
| เริ่มต้น | อ่าน HTTP request/response; หน้าจอและปุ่ม; แยกความพยายามโจมตีกับผลกระทบ |
| กลาง | เชื่อม session/เวลา/การเข้าถึงข้อมูล; ตรวจ change record และ scope; note/assessment/evidence และข้อจำกัด AI |
| ชำนาญ | baseline/anomaly; สมมติฐานและหลักฐานที่ขัดกัน; ตรวจ AI/RAG citations และเตรียมส่งผลวิเคราะห์ |

บทเรียนเริ่มต้นที่เผยแพร่เดิมถูกคงเนื้อหา ID และ version ไว้เหมือนเดิมทุกประการ
บทอื่นใช้ UUID ใหม่ ไม่แก้ทับ published content หรือ progress เก่า
ทุกบทมีรูปแบบตรงกับ `LessonView` ปัจจุบัน แต่ wrapper ของไฟล์เป็นชุดเนื้อหาใหม่สำหรับเตรียมทดสอบ

## ขอบเขตที่สำคัญ

- ต่อไฟล์นี้เข้าหน้า **preview** `/demo/learning` แล้ว; `/learning` และ API ของบัญชีจริงยังใช้บทเรียนในฐานข้อมูลตามเดิม
- Preview เป็นตัวอย่างฝึกสาธารณะสำหรับตรวจเนื้อหา ไม่ใช้เป็นการยืนยันสิทธิ์เรียนหรือผ่านระดับจริง
- หน้า preview ไม่ตรวจ session ไม่เรียก auth/domain API และไม่มี form ที่ส่งข้อมูลออกไป; เปิดโดยตรงได้แม้ backend ไม่พร้อม
- ไม่เพิ่ม migration ไม่เรียก seed operator ไม่เชื่อม PostgreSQL หรือ Supabase และไม่เปลี่ยนข้อมูลบัญชีใด
- ไม่ใส่คะแนน สถานะผ่าน unlock หรือ session ใน JSON และไม่ใช้ localStorage ทดแทนข้อมูล authoritative
- ฝึกรวมมี 3 เคสจาก `practice-v1.json` ทุก event แสดงทันที ไม่ใช่ simulation runner และไม่มี future events
- ร่างการวิเคราะห์เก็บใน React memory เท่านั้น สลับเคสในแท็บฝึกแล้วกลับมาได้ แต่ refresh/ออกจากหน้านั้นร่างหาย
- ปุ่มตรวจร่างตรวจเพียงกรอกครบ ไม่ตัดสินความถูกต้อง ไม่เรียก evaluator ไม่เพิ่มข้อสอบ ไม่แก้ rubric, retake, quota หรือสิทธิ์
- ไม่เรียก Dify หรือ provider จริง และไม่ index ไฟล์นี้เข้า RAG โดยอัตโนมัติ
- ไม่ถือว่าการกดอ่าน 3 ระดับใน preview ทำให้ server-side gates/exams หรือทั้งระบบผ่าน acceptance

## การแก้เนื้อหาและ sync ไปหน้า preview

แก้ต้นฉบับ backend JSON แล้วรันจาก `frontend/`:

```bash
node scripts/sync-curriculum.mjs
node scripts/sync-curriculum.mjs --check
node --test tests/curriculum.test.mjs
```

Exporter คัดลอกเฉพาะไฟล์ training นี้ ไม่ค้นหรือ export `fixtures/` ทั้งโฟลเดอร์
CI ตรวจว่าสำเนาตรงกับต้นฉบับ; build frontend แบบแยกไม่ต้องมี backend source
อย่าใส่ exam bank, answer keys, secret หรือข้อมูลบัญชีจริงในไฟล์ public

## วิธีตรวจไฟล์โดยไม่ใช้ฐานข้อมูล

จาก `backend/` เมื่อมี runtime ตาม lockfile แล้ว:

```bash
uv run --frozen pytest tests/test_curriculum_fixture.py -q
```

Tests ตรวจ JSON keys ซ้ำ, ลำดับระดับ, UUID ไม่ซ้ำ, lesson/level references,
โครงสร้างทุกบทด้วย Pydantic `LessonView`, ข้อจำกัดทุกขั้น และความตรงกับบทเรียนที่เผยแพร่เดิม
รวมถึงการไม่มี fields สำหรับเฉลยสอบหรือผลบัญชีจริง

### ผลตรวจ local วันที่ 21 ต.ค. 2026

ฐาน source `126612d` พร้อมไฟล์เนื้อหา/tests ใน working tree นี้ ตรวจด้วย image
`soc-backend-auto-login-test:local`, mount `backend/` แบบ read-only และ `--network none`
ไม่มี secrets หรือการเชื่อม DB:

- `python -m pytest tests/test_curriculum_fixture.py tests/test_learning.py -q -p no:cacheprovider`: **9 passed**
- `ruff check tests/test_curriculum_fixture.py`: ผ่าน
- `ruff format --check tests/test_curriculum_fixture.py`: ผ่าน

ผลรอบไฟล์ JSON นี้ตรวจโครงสร้างและ regression ของเนื้อหาเท่านั้น
ผล browser/build หลังเชื่อม preview แยกอยู่ใน [รายงาน preview](learning-preview-verification.md)
ยังไม่ใช่การตรวจคุณภาพบทเรียนกับผู้เรียนจริง; GitHub CI ของงานนี้ยังรอยืนยัน

## ลำดับสำหรับตรวจเนื้อหา

1. เริ่มที่ระดับเริ่มต้น อ่าน Method/Path → Response → บัญชี/IP → Timeline → ข้อจำกัด
2. อ่านบทหน้าจอ/ปุ่ม แล้วตรวจว่าผู้เรียนแยกบันทึกขั้นเรียน จบบทเรียน และส่งข้อสอบได้
3. อ่านตัวอย่าง 401/403 และฝึกอธิบายว่าอะไรยืนยันได้หรือยังยืนยันไม่ได้
4. ระดับกลางให้จับคู่ session, ตรวจ response/ปริมาณข้อมูล และตรวจ change ทั้งเวลา/asset/scope
5. ระดับชำนาญให้เทียบ baseline, ตั้งสมมติฐานอื่น, ตรวจแหล่งหลักฐานอิสระ และฝึกส่งต่อเมื่อยังไม่แน่ใจ
6. ตรวจว่าแยก event evidence กับความรู้ RAG ได้ ไม่เชื่อ AI เพียงเพราะมี citation

กดตามลำดับนี้ได้ในหน้า preview แล้ว เลือกบทจาก dropdown หรือสารบัญ
กดตัวอย่างเพื่อเปิดคำอธิบาย แล้วไปขั้น/บทถัดไป URL เก็บบทและขั้นที่เลือกเท่านั้น
เลือกแท็บฝึกรวมเพื่ออ่าน event เลือกหลักฐานและร่างข้อสรุปโดยไม่ให้คะแนน
ก่อน import ใช้กับบัญชีจริงต้องทดสอบ prerequisite ครบทุกบท, version/progress compatibility,
exam bank แยกจาก training และการปลดล็อกทุกระดับกับ server จริง โดยไม่ seed ผลผ่านปลอม
Supabase ยังไม่ได้เชื่อมในงานนี้

## AI/RAG ใน flow

หน้า `/demo/learning?view=ai` อธิบายตำแหน่งใช้งาน:

1. ช่วงเรียน: ถามหลักการจาก approved corpus ไม่ใช่เฉลยสอบ
2. ช่วงฝึก: ใช้ authorized frozen evidence + ความรู้ที่ค้นได้ ช่วยตรวจข้อสรุป โดยไม่แก้ human assessment
3. ก่อนส่งข้อสอบ: ปิด Ask AI/คำใบ้/เฉลย
4. หลังส่ง: freeze ก่อนประเมินด้วยกฎและ AI/RAG ตาม rubric; กำกวม/ล่ม/อ้างอิงผิดให้ `needs_review` และคนตรวจ

Preview แสดงคู่มือแบบเลือกข้อความตายตัวจาก JSON เท่านั้น **ไม่ใช่ retrieval/RAG หรือ mock grading**
ปุ่มถาม AI ปิดและระบุว่ายังไม่เชื่อม Dify ไม่มี outbound calls หรือค่าใช้จ่าย
การเชื่อมจริงยังต้องกำหนด workflow/corpus/citations/revocation/usage/budget และ credentials ฝั่ง server
