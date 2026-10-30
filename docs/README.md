# คู่มือของโครงการ SOC

> **หมายเหตุสถานะปัจจุบัน:** การกล่าวถึง Gemini ในเอกสารนี้เป็นข้อมูลย้อนหลัง ปัจจุบัน local Supabase stack เปิด Dify Workflow เดียวสำหรับผู้ช่วยสอนและ feedback ข้อเขียนแล้ว (ตรวจ 30 ต.ค. 2026) ดู [ผลตรวจ](shared-dify-workflow-verification.md) ส่วน AI วิเคราะห์รอบฝึกยังเป็น mock และยังไม่มี public deployment

หน้านี้ช่วยเลือกเอกสารตามสิ่งที่ต้องการอ่าน เอกสารอธิบายทั้งเป้าหมาย วิธีพัฒนา และผลตรวจจริง จึงควรดูวันที่กับสถานะในแต่ละไฟล์เสมอ เพราะแผนที่เขียนไว้ไม่ได้แปลว่าระบบทำเสร็จแล้ว

## ถ้าเพิ่งเข้ามาอ่าน

เริ่มจาก [ระบบและแผนภาพล่าสุด](current-system.md), [วิธีเล่น/สคริปต์นำเสนอ](presentation-guide.md)
และ [ตรวจ Deliverables](presentation-readiness.md) สำหรับสถานะ working tree 27 ต.ค. 2026

1. [ภาพรวมโครงการและข้อจำกัด](soc-simulation.md)
2. [เส้นทางเรียนและข้อสอบ](learning-path.md)
3. [สถาปัตยกรรมระบบ](architecture.md)
4. [รายการงานและสถานะปัจจุบัน](implementation-checklist.md)

## วิธีเปิดและพัฒนา

งาน Dify ล่าสุด: [การตั้งค่า](dify-configuration.md) · [ขอบเขต/ผลตรวจ Tutor](dify-integration-verification.md) · [วิธีทดสอบทุก Flow](end-to-end-test-plan.md)

ผลแก้ UI ล่าสุด: [Learning โหลดซ้ำและร่างคำถาม AI](learning-loading-verification.md)

ผลตรวจความปลอดภัยของข้อมูล: [Data validation และ regression coverage](data-validation-verification.md)

ผลเชื่อม Workflow เดียวสองโหมด: [Tutor + feedback ข้อเขียน](shared-dify-workflow-verification.md)

ให้เพื่อนทดลอง/ร่วมพัฒนา: [URL สาธารณะต่างจาก clone รันเองอย่างไร](friend-testing.md)

| เอกสาร | ใช้เมื่อ |
|---|---|
| [เริ่มระบบในเครื่อง](local-development.md) | เปิดเว็บ API และ PostgreSQL ด้วย Docker หรือเตรียมฐานข้อมูล local |
| [เริ่มต้นโค้ดและเวอร์ชันเครื่องมือ](getting-started.md) | ตรวจ runtime และคำสั่งทดสอบพื้นฐาน |
| [ตั้งค่าบัญชีผู้ใช้](auth-development.md) | ทำความเข้าใจสมัครสมาชิก เข้าสู่ระบบ และ Guest demo |
| [ย้ายไป Supabase](supabase-migration.md) | PostgreSQL/Auth bridge, operator/runtime แยก และเงื่อนไข Google/confirmation |
| [ผลตรวจ Supabase](supabase-verification.md) | live DB/health ที่ตรวจแล้ว เทียบกับ fake-provider tests และข้อที่ยังต้องตรวจจริง |
| [พัฒนาสถานการณ์ฝึก](scenario-development.md) | เพิ่มหรือแก้ fixture ของสถานการณ์จำลอง |
| [ตรวจ CI ในเครื่อง](ci-local.md) | รัน checks ก่อนส่งขึ้น GitHub |
| [แผน CI/CD](ci-cd.md) | อ่านแผน build, staging, release และ rollback; ส่วนที่ยังไม่มีระบบรองรับจะระบุว่าเป็นแผน |
| [วิธีดูหน้า preview](render-preview.md) | ตรวจขอบเขตของ preview ที่เปิดอยู่ |

## แบบระบบและข้อกำหนด

| เอกสาร | ใช้เมื่อ |
|---|---|
| [Architecture](architecture.md) | ดูว่าส่วนเว็บ API worker และ evaluator ติดต่อกันอย่างไร |
| [API contract](api.md) | ดู endpoint, request/response, สิทธิ์ และสถานะ approved/draft |
| [Database](database.md) | ดูตาราง ความสัมพันธ์ transaction และ migrations |
| [RAG design เดิม](rag-langchain.md) | แบบออกแบบ/หลักฐานของ pipeline ภายในที่ยังอยู่ใน source; ทิศทางผลิตภัณฑ์ปัจจุบันคือเรียกบริการภายนอกผ่าน API |
| [RAG local guide เดิม](rag-development.md) | คู่มือของ pipeline ภายในและการทดสอบในเครื่อง; ยังไม่ใช่คู่มือเชื่อม Dify |
| [SRS](srs.md) | อ่านข้อกำหนดและนโยบายที่ยังรอการตัดสินใจ |
| [Prototype alignment](prototype-alignment.md) | เทียบ prototype กับระบบจริงและดูความต่าง |
| [Password reset plan](password-reset-plan.md) | อ่านแผนร่างสำหรับระบบลืมรหัสผ่าน |
| [Google login setup](google-login-setup.md) | ดูสถานะและข้อจำกัดการเชื่อม Google login |

## รายงานผลตรวจ

สถานะบทเรียน/แบบฝึก DB ล่าสุด: [Database training](database-training.md)
ใช้แทนหน้า runtime JSON เดิม รายงาน preview ด้านล่างเป็นประวัติ ไม่ใช่ runtime ปัจจุบัน

ประวัติ preview JSON เดิม (เลิกใช้เป็น runtime แล้ว; `/demo/learning` redirect ไปหน้าที่ใช้ DB):
[คู่มือเนื้อหา seed](learning-content-seed.md) · [ผลตรวจ preview](learning-preview-verification.md)

[แก้เริ่มรอบฝึกแล้ว error หาย](run-start-feedback-verification.md)

[แก้ CI browser selectors ให้ตรง UX ปัจจุบัน](ci-browser-selector-verification.md)

รายงานเหล่านี้เป็นบันทึกตามวันที่และ commit ที่ระบุในแต่ละไฟล์ ไม่ได้ยืนยันสภาพแวดล้อมอื่นหรือ commit ใหม่กว่า:

- [คู่มือรวมข้อ 01–19 พร้อมคำอธิบายและรายงานต้นฉบับฉบับเต็ม](all-step.md)

- [ข้อ 01–05](step-01-verification.md) · [ข้อ 06–10](step-06-10-verification.md)
- [ข้อ 11](step-11-verification.md) · [ข้อ 12](step-12-verification.md) · [ข้อ 13](step-13-verification.md)
- [ข้อ 14: RAG และข้อที่ยังต้องตรวจ](step-14-verification.md) · [คู่มือผู้ตรวจ](step-14-review-guide.md) · [agent self-review](step-14-agent-review.md)
- [ข้อ 15: บทเรียน](step-15-verification.md) · [ข้อ 16: ข้อสอบ](step-16-verification.md) · [ข้อ 17: การตรวจคำตอบ](step-17-verification.md)
- [ข้อ 18: staging](step-18-verification.md) · [ข้อ 19: acceptance](step-19-verification.md)
- [ตรวจหน้า responsive](frontend-responsive-verification.md) · [ตรวจความสอดคล้องระหว่างโค้ดกับเอกสาร](implementation-alignment-review.md)

## เรื่องที่ควรจำ

- ระบบใช้ข้อมูลฝึกจำลอง ไม่เชื่อม SIEM/EDR ขององค์กร
- บทเรียนและข้อสอบจริงต้อง login; การทำบทเรียนจบไม่เท่ากับสอบผ่าน
- AI ไม่ให้คะแนนผ่านหรือปลดล็อกระดับเอง
- ผู้ช่วยสอนและ feedback ข้อเขียนเรียก Dify ผ่าน API/worker จริงใน local Supabase stack; ส่วน RAG ภายในเก่ายังอยู่ใน source และ AI วิเคราะห์รอบฝึกยังเป็น mock
- Gemini adapter เก่ายังเก็บใน source/รายงานเพื่ออ้างอิง แต่ provider config ปัจจุบันปฏิเสธ `gemini_free`; Tutor และ feedback ข้อเขียนใช้ Dify ใน local Supabase stack ส่วน AI วิเคราะห์รอบฝึกยังใช้ mock
- RAG quality acceptance, staging และ production ยังมีงานค้าง ดู checklist ก่อนอ้างว่าพร้อมใช้
- [Prototype](../prototype/README.md) เป็นงานอ้างอิงแยกจากเว็บแอป และเก็บข้อมูลไว้ใน browser

## คำศัพท์ที่เจอบ่อย

| คำ | ความหมายแบบสั้น |
|---|---|
| API | ช่องทางที่หน้าเว็บใช้คุยกับ backend |
| Backend | ระบบหลังบ้านที่ตรวจสิทธิ์และจัดการข้อมูล |
| Fixture | ชุดเหตุการณ์จำลองสำหรับฝึกและทดสอบ |
| Migration | ไฟล์ที่ค่อย ๆ เพิ่มหรือปรับโครงสร้างฐานข้อมูล |
| Mock | ตัวแทนจำลองที่ใช้ทดสอบแทนการเรียก provider จริง |
| Embedding / vector | ตัวเลขที่แทนความหมายของข้อความ เพื่อค้นข้อความใกล้เคียง |
| Retrieval | การค้นเอกสารที่เกี่ยวข้องก่อนส่งบริบทให้ AI |
| Citation | ที่มาของข้อความหรือข้อมูลที่ AI อ้าง |
| RAG | วิธีให้ AI ใช้เอกสารที่ค้นพบเป็นบริบทก่อนตอบ |
| Staging | ระบบทดสอบที่ใกล้เคียง production ก่อนเปิดใช้งานจริง |
| Acceptance | การตรวจว่า feature ทำงานตามเกณฑ์ที่ตกลงไว้ |

ชื่อ API, status และ identifier ใน code block คงเป็นภาษาอังกฤษเพื่อให้ค้นในโค้ดได้ตรงกัน
