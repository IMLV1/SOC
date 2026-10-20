# RAG development status

> **ทิศทางปัจจุบัน:** ใช้บริการ RAG ภายนอก Dify เพียงรายเดียว โดย repository เรียกผ่าน API. ไม่เรียก Gemini โดยตรง. Runtime ใช้ mock จนกว่าการเชื่อม Dify จะผ่านการทดสอบ

## สถานะใน checkout นี้

มี Dify Chat API client ฝั่ง backend ที่ทดสอบด้วย mock แต่ยังไม่ต่อกับ worker/API flow. ยังไม่มี Dify Base URL หรือ app key ในเครื่อง และไม่มีการเรียกบริการจริง. การตั้ง `SOC_AI_PROVIDER=dify` ยังไม่ทำให้ระบบเรียก Dify; worker จบงานด้วย `DIFY_ANALYSIS_ADAPTER_UNAVAILABLE`. หากตั้ง `SOC_KB_ENABLED=true` การเริ่ม run จะถูกปฏิเสธด้วย `DIFY_RAG_ADAPTER_UNAVAILABLE` เพื่อไม่ให้ pipeline RAG ภายในเดิมถูกใช้แทน Dify

ไฟล์ secret local ที่เตรียมไว้ชื่อ `.local/secrets/dify_app_key.txt`; เก็บ key ไว้ในไฟล์นี้เมื่อมี config ที่อนุมัติแล้วเท่านั้น. ห้ามใส่ key ในแชต, `.env`, frontend, logs หรือ Git. ยังไม่มีการอนุมัติค่าใช้จ่ายหรือ environment สำหรับ real calls

## งานที่ต้องเสร็จก่อนเปิดใช้

1. เชื่อม Dify Chat API ใน worker โดยยึด secret ฝั่ง server และไม่เรียก provider ใน DB transaction
2. กำหนด app/workflow input/output schema สำหรับ triage และคำถาม; ตรวจ Pydantic schema และ citation subset ก่อนบันทึก
3. กำหนดการแทน Dify document/segment citations เป็น snapshot ที่อ้างอิงได้, ตรวจสิทธิ์และ revocation ในทุก read/retry/export
4. กำหนด usage unknown, quota reservation, timeout และ retry ให้ไม่เดาการใช้เป็นศูนย์หรือเรียกซ้ำโดยไม่ตั้งใจ
5. เพิ่ม migration/API/UI integration tests ด้วย fake Dify responses; ทดสอบ PostgreSQL integration และ held-out Thai/English quality review
6. ตั้ง Dify Base URL, app key, privacy และ budget ใน environment ที่ได้รับอนุมัติ แล้วค่อยทำ bounded smoke test

จนกว่าข้อข้างต้นจะผ่าน อย่าติ๊ก checklist ว่าเชื่อม provider หรือ RAG สำเร็จ

## หลักฐานย้อนหลัง

ผลที่เคยวัดจาก local pgvector/Gemini และ artifacts ใน [รายงานข้อ 14](step-14-verification.md) เป็นประวัติของ implementation ก่อนเลือก Dify. ไม่ใช่ผลทดสอบ Dify และไม่ใช่คำสั่งให้เรียก Gemini ซ้ำ. ดู [เอกสาร design เดิม](rag-langchain.md) เพื่อเข้าใจ schema ที่ยังต้องประเมิน/ย้ายออกจาก runtime.
