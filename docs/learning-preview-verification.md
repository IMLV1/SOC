# ผลตรวจ JSON learning preview

วันที่ 21 ต.ค. 2026 บนฐาน `126612d` และ working tree ของงานนี้ ยังไม่ commit/push
ขอบเขตคือ preview จากไฟล์ตามคำขอ ไม่ใช่การตรวจรับทุกระบบหรือ production

## พฤติกรรม

- `/demo/learning` เปิด 3 ระดับ / 9 บท / 45 ขั้นจากสำเนา public ของ training JSON
- เลือกบทจากสารบัญ/dropdown กด target เพื่อเปิด explanation/limitation และกดไปขั้น/บทถัดไป
- URL เก็บ lesson/step ที่เลือกเพื่อ refresh/deep link; ไม่เก็บคะแนนหรือ progress บัญชี
- `/demo/learning?view=practice` เปิด 3 ตัวอย่างพร้อมตัวกรองระดับ เลือก evidence และเขียน draft
- สลับเคสเก็บ draft ใน React memory แต่ refresh/ออกจากแท็บฝึกทำให้หาย ไม่มี localStorage
- ตรวจร่างเฉพาะช่องที่จำเป็น ไม่ให้คะแนน ไม่สร้างผลผ่าน ไม่เรียก AI
- แหล่งคำแนะนำเป็นบทเรียน JSON ที่ระบุที่มา ไม่อ้างว่าเป็น RAG; Dify ยังปิด
- `/demo/learning?view=ai` อธิบาย learning/training/pre-submit/post-submit boundary
- SessionProvider ไม่เรียก auth API บน route นี้; โหมดบัญชีจริงและ API เดิมไม่ถูกแทนที่
- คง `prototype/` และฐานข้อมูลเดิม ไม่เรียก migration/seed/provision หรือ provider จริง

## การตรวจ local

Runtime: frontend image `soc-frontend-check:local` ใช้ Node ที่ปักไว้ใน repository;
browser ใช้ Playwright ของ repository กับ Chrome ที่ติดตั้งในเครื่อง ไม่ดาวน์โหลด browser ใหม่

- `node frontend/scripts/sync-curriculum.mjs --check`: สำเนาตรงกับต้นฉบับ
- `node --test tests/curriculum.test.mjs`: **5 passed**
- `npm run lint`: ผ่าน
- `npm run typecheck`: ผ่าน
- Production build ใน container แยก `--network none`: ผ่าน รวม TypeScript/static generation
- `node --test tests/assets.test.mjs` หลัง production build: **1 passed**, ไม่พบ forbidden fixture/truth payloads
- Browser `curriculum-preview.spec.ts`: **3 passed** หลัง frontend dev server reload route ใหม่
  ตรวจทั้ง 45 ขั้น, refresh, draft/filter, escaped `<sample>`, AI unavailable และ API requests เป็นศูนย์
- รันร่วมกับ `learning-interaction.spec.ts`: **4 passed** รวม regression ของหน้าบัญชีเดิมผ่าน mocked API
- Responsive 375/768/1440px: ตรวจ overflow ทั้งบทเรียน/เคสฝึก และ keyboard Enter เพื่อเปิดคำอธิบาย
  ตรวจ screenshot desktop/mobile เพิ่ม ไม่ใช่ accessibility audit เต็มรูปแบบ
- `python3 scripts/check-doc-links.py` และ `git diff --check`: ผ่าน

Browser tests บล็อก `/api/**` ทุก request เพื่อไม่เชื่อมฐานข้อมูล
รอบแรก host ไม่มี Playwright Chromium ที่คาดไว้ จึงใช้ Chrome ที่มีอยู่แทน
รอบแรกหลังเพิ่ม route ได้ 404 เพราะ dev container ยังไม่รับไฟล์ใหม่;
รีสตาร์ตเฉพาะ frontend แล้วทดสอบใหม่ผ่าน ไม่ restart/แก้ PostgreSQL

## ยังไม่พร้อม

ไม่มี server-backed progress/gate/exam สำหรับบทใหม่จากงานนี้ ไม่มี Dify integration หรือ AI grading จริง
การเปิดทุกระดับใน preview ไม่ใช่สิทธิ์ข้ามระดับของผู้เรียนจริง
ยังต้องตรวจคุณภาพเนื้อหากับผู้เรียน เชื่อม lesson versions/required lessons และฝึก/สอบหลายระดับกับ backend
ทดสอบ migrations/roles/persistence เมื่อ environment ที่ผู้ใช้เลือกพร้อม
Supabase ยังไม่เชื่อม GitHub CI ของ SHA ใหม่ staging/production และข้อ 18–19 ยังรอยืนยัน
