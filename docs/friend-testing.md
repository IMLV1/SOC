# ให้เพื่อนลอง Sentinel

## เพื่อนเป็นผู้ทดลองใช้งาน

วิธีที่เหมาะคือส่ง **URL เว็บที่ deploy แล้ว** พร้อมวิธีสมัคร/เข้าสู่ระบบและรายการที่อยากให้ลอง ไม่ต้องให้ source code, Docker, `.env`, DB password หรือ Dify API key

ตอนนี้ `http://127.0.0.1:4175` เป็นเว็บบนเครื่องผู้พัฒนา เพื่อนเปิด URL นี้จากเครื่องตนเองจะไม่ได้เข้ามาที่เครื่องผู้พัฒนา การ push GitHub ไม่ได้ทำให้ URL นี้เป็นเว็บสาธารณะ และไม่ได้ย้าย API/worker/evaluator หรือ secrets ขึ้น hosting

หลัง deploy ให้ส่งเพื่อน:

1. URL เว็บ HTTPS และวิธีสมัครบัญชี Analyst ของตนเอง
2. ลำดับทดลอง: เรียน → บันทึกขั้น/refresh → ฝึกเลือกหลักฐานและส่งคำตอบ → ถาม AI → simulation → สอบเมื่อเรียนครบ
3. ข้อจำกัด: AI เป็นผู้ช่วยสอน ไม่ให้คะแนนสอบ/ปลดล็อกระดับ, ปิดระหว่างสอบ, โควตา 20 logical requests/คน/วัน UTC และงบรวม US$0.25/วัน ยังขึ้นกับโควตา provider
4. วิธีแจ้งบั๊ก: หน้าที่เปิด/ขั้นตอน/ผลที่คาด/ผลที่พบ/เวลา/browser และภาพที่ปิดบังข้อมูลลับแล้ว ห้ามส่งรหัสผ่าน token หรือ cookie

ตรวจรายการเต็มใน [คู่มือทดสอบ Flow](end-to-end-test-plan.md) อย่าใช้บัญชีร่วมกัน และอย่าแก้คะแนนใน DB เพื่อให้ demo ผ่าน

## เพื่อนเป็นผู้ร่วมพัฒนาและต้องการรันโค้ดเอง

ส่ง repository `https://github.com/IMLV1/SOC` สาขา `main` และคู่มือนี้ หาก repository เป็น private ต้องเพิ่มสิทธิ์ collaborator แยก ไม่ส่ง credentials เจ้าของบัญชี

ต้องมี Git, Python 3 สำหรับ script เตรียม local secrets และ Docker Desktop/Engine พร้อม Compose จากนั้น:

```bash
git clone https://github.com/IMLV1/SOC.git
cd SOC
python3 scripts/init-local.py
docker compose config --quiet
docker compose up --build -d
docker compose ps -a
```

Windows ใช้ `python scripts/init-local.py` แทน `python3` ได้ เปิด `http://127.0.0.1:3000` บนเครื่องเพื่อนเอง แล้วสมัครบัญชีใหม่

ชุดนี้สร้างฐานข้อมูลและ local authentication ของเพื่อนเอง ไม่ใช้บัญชี/ความคืบหน้าจาก Supabase เครื่องผู้พัฒนา และเริ่ม AI แบบ mock/lesson Tutor disabled ไม่ใช่ real Dify หรือ Google login อัตโนมัติ การ seed/migrate เป็น one-shot; exit 0 คือสำเร็จ

ถ้าอัปเดต checkout เดิม ให้ตรวจงานที่ยังไม่ commit ก่อน `git pull --ff-only origin main` ไม่ reset หรือลบ volumes เพื่อให้เปิดได้ ห้ามใช้ `docker compose down -v` กับข้อมูลที่ต้องการเก็บ

ดูรายละเอียด [local development](local-development.md), [Supabase](supabase-migration.md) และ [Dify configuration](dify-configuration.md) หากต้องการต่อบริการจริงให้ผู้ดูแลตั้ง secrets/release ผ่านช่องทางส่วนตัวและตรวจสิทธิ์ก่อน ไม่คัดลอก `.local/`, `.env*` ที่มีค่าจริง หรือ migration-owner/postgres credentials ให้ผู้ทดลองใช้งาน
