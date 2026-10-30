# Dify Cloud configuration

**อัปเดต 30 ต.ค. 2026:** Publish Workflow รุ่นเดียวที่รับ `mode=tutor|grade` แล้ว; local Supabase stack ใช้ migration 0024 และ policy version 3 เปิดทั้งสองโหมดผ่าน API/worker ดู [ผลตรวจจริงและข้อจำกัด](shared-dify-workflow-verification.md) ข้อความสถานะวันที่ 28 ต.ค. ด้านล่างเป็นประวัติ

อัปเดต 28 ต.ค. 2026: Base URL ที่ผู้ใช้ระบุคือ `https://api.dify.ai/v1`
ค่าเริ่มต้นใน DifyConfig/provider config และ Compose ใช้ URL นี้ โดย override `DIFY_API_BASE_URL` เพื่อใช้ instance อื่นได้
ถ้าตั้งเป็นข้อความว่างใน Python config จะถูกปฏิเสธ ไม่ถือว่าเป็น URL ที่ถูกต้อง

## สิ่งที่ตั้งแล้ว

28 ต.ค. 2026 รอบเปิด: lesson Tutor ใช้ Published-latest Workflow ผ่าน `/workflows/run` และตรวจ workflow_id หลังตอบกลับตามที่ผู้ใช้อนุมัติสำหรับ Free เปิด policy version 2 เฉพาะ local stack แล้ว ไม่ใช่การ deploy สาธารณะ ไม่ได้เปลี่ยน investigation provider หรือ evaluator เป็น real AI

```text
DIFY_API_BASE_URL=https://api.dify.ai/v1
SOC_AI_PROVIDER=mock
SOC_KB_ENABLED=false
```

URL สาธารณะนี้ไม่ใช่ API key และไม่เปิดการเรียก provider โดยตัวเอง
`DIFY_APP_KEY_FILE` เป็น path ของ ignored secret file ฝั่ง server สำหรับ client เดิม ห้ามใส่ key ลง source, frontend/NEXT_PUBLIC หรือแชต
ใช้ `compose.dify.yaml` เพิ่ม secret mount เฉพาะ API/worker ได้ แต่ไม่เปิด Tutor policy หรือเปลี่ยน investigation provider จาก mock อัตโนมัติ

## ขอบเขตที่เชื่อม

client เดิม `app/knowledge/dify_client.py` เรียก `/chat-messages` สำหรับ Chat API
เพิ่ม `app/knowledge/dify_workflow.py` และ `app/tutor/` สำหรับ Published-latest Workflow API พร้อม `inputs.question` และตรวจ response version แล้ว ใช้กับผู้ช่วยสอนใน `/learning` โค้ด `grade` สำหรับ feedback ข้อเขียนใช้ endpoint/key/Workflow เดียวกันโดยส่ง `inputs.mode=grade` หลัง submit เท่านั้น; ยังไม่ใช่คะแนนสอบหรือ triage ดู [ผลตรวจสองโหมด](shared-dify-workflow-verification.md)

ก่อนเปิดจริงต้องกำหนด published workflow, task/input/output schema, authorized evidence snapshot, citations/revocation, quota/usage/budget และ key ฝั่ง server
ผล Ask AI ต้องผ่าน validation ก่อนบันทึก ไม่ใช้ข้อความตอบจาก LLM ปลดล็อกระดับหรือให้คะแนนสอบโดยตรง

ก่อนแก้/Publish Flow เปลี่ยน credentials, retrieval หรือ plan ให้ปิด Tutor policy แล้วตรวจ release/cost ใหม่ การตรวจ response version เกิดหลัง dispatch จึงไม่ป้องกันการเรียก Flow ใหม่ครั้งแรก เมื่อพบ mismatch ระบบหยุดรับคำถามใหม่จน operator อนุมัติ policy version ใหม่ ไม่ fallback/retry เอง

เปิด policy ด้วย one-shot `python -m app.tutor.release --review-file <review.json> --expected-version <current>` บน migration_owner เท่านั้น ไม่ใช้ runtime role/ไม่ทำใน startup มี CAS และ before/after audit คำสั่งนี้ไม่เปลี่ยน schema; migration 0023 ยังคงเดิม

## เปิด stack พร้อม secret mount (ยังไม่เปิด paid dispatch)

```bash
docker compose --env-file .local/supabase/runtime.env \
  -f compose.supabase.yaml -f compose.dify.yaml up -d --no-deps api worker evaluator
```

ใช้หลัง migration wrapper อัปเดต 0023 และ image ทั้งสามบริการรองรับแล้ว ไม่รัน migration/seed ใน startup
`app.tutor_policy` เริ่ม enabled=false; ต้องมี reviewed workflow/corpus/chunk hashes/cost bound ก่อน operator เปิด โหมด `grade` เริ่ม `grade_enabled=false` แม้ Tutor เปิดอยู่
ผู้ใช้ยกเลิกเพดานรวม US$0.25/วันเมื่อ 29 ต.ค. 2026; migration 0024 ลบคอลัมน์และ hard gate นี้ แต่ยังคงโควตา 20 logical AI requests/ผู้ใช้/วันและบันทึก reserved/usage ต่อคำขอ การใช้จริงยังขึ้นกับโควตา/เงื่อนไขของ Dify และ model provider

## การตรวจรอบนี้

เพิ่ม regression ตรวจ cloud URL default, custom URL override, missing secret path/blank URL และยืนยันว่า URL ไม่เปลี่ยน default provider จาก mock
tests ใช้ fake HTTP/ปิด network ไม่เรียก Dify จริง ผลคำสั่งสรุปในข้อความส่งมอบ ไม่ถือว่า integration หรือ benchmark ผ่านจากการตั้ง config นี้
