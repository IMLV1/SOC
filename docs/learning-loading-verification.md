# ผลตรวจการโหลดหน้า Learning — 29 ต.ค. 2026

ตรวจ working tree บน `main` ที่มี base commit `bd3c903` รายงานนี้เป็นผล local ไม่ใช่ผล GitHub CI หรือ deployment

## สาเหตุและการแก้

SessionProvider ตรวจ session เมื่อกลับมาโฟกัสและทุก 60 วินาที โดยได้ session object ใหม่ แม้เป็นบัญชีเดิม หน้า Learning เดิมใช้ object นี้เป็น dependency จึงโหลดบทเรียนใหม่และถอด LessonTutor ออกจากหน้า ทำให้ร่างคำถามหาย นอกจากนี้การโหลดบทเรียนยังรอสถานะข้อสอบที่เรียกแยกตามลำดับ

- ใช้ user identity เป็น dependency และ reset workspace เมื่อบัญชี/role/status เปลี่ยน
- แยกการโหลดบทเรียนกับสถานะข้อสอบ บทเรียนอ่านได้ขณะรอตรวจสอบ แต่ไม่ให้ส่ง AI หรือเริ่มสอบก่อนตรวจสิทธิ์สำเร็จ
- คงบทเรียนเดิมขณะ refresh ความคืบหน้า และคง LessonTutor เมื่อเปลี่ยนบทเรียน
- ปฏิเสธผลตอบกลับที่ล้าสมัยเมื่อเปลี่ยนบทเรียนหรือเปลี่ยนคำขอ
- การ polling งาน AI ยังทำตามเดิมและไม่โหลดบทเรียนทั้งหน้า

ร่างที่ยังไม่ส่งอยู่ใน React state ไม่เพิ่ม localStorage หรือฐานข้อมูลใหม่ เมื่อเปลี่ยนบัญชีร่างเดิมจะถูกล้าง

## ผลตรวจ

ก่อนแก้ reproduce ได้สองกรณี: focus แล้วร่างหาย และสถานะสอบช้าทำให้บทเรียนไม่แสดง

หลังแก้:

- `npm run lint` ผ่าน
- `npm run typecheck` ผ่าน
- `npm run build` ผ่านใน container แยกจาก dev
- `node --test tests/assets.test.mjs` ผ่าน 1 test
- Playwright ผ่าน 14 tests ใน `learning-loading.spec.ts`, `lesson-tutor.spec.ts`, `learning-interaction.spec.ts`, `learning-progression.spec.ts`, `exam-review.spec.ts`
- `git diff --check` ผ่าน

Regression ใหม่ 7 tests ครอบคลุม focus/60-second refresh, AI polling, exam status ล้มเหลวและตรวจใหม่, background progress refresh, exam status ช้า, สลับบทเรียนเร็ว และเปลี่ยนบัญชี ใช้ API จำลองเพื่อควบคุมลำดับ response; ไม่เรียก Dify จริง

ใช้ Docker dev frontend ที่ port 4175 และ Chromium ใน container ทดสอบแยก ไม่มีการเปลี่ยน schema, migrations, provider config หรือ scoring policy

## ข้อจำกัด

ลองรัน `learning.spec.ts` ที่ต้องใช้ backend จริงด้วย แต่ไม่ผ่านขั้นสมัครสมาชิก/redirect ไป `/account` ใน environment นี้ จึงไม่อ้างว่าทดสอบ flow จริงตั้งแต่สมัครถึงสอบผ่านแล้ว ชุด API จำลอง 14 tests ที่ระบุด้านบนผ่านครบ การตรวจ GitHub CI และ deployed acceptance ยังรอยืนยัน
