# แก้ CI browser selectors — 29 ต.ค. 2026

ฐานงาน `29dace804d89a72325c6d40ec920b5e4240eafef`, branch `codex/fix-ci-29dace8`
เป็นการแก้ browser tests บนเวอร์ชันที่ผู้ใช้เลือก ไม่ได้นำ investigation implementation
หรือ migration 0024 กลับเข้า branch นี้

## ขอบเขต rollback ของ PR

remote `main` มี merge `afbbe02` ของ PR #20 อยู่แล้ว การแตก branch จาก commit เก่า
อย่างเดียวจะไม่ลบ feature นั้นเมื่อ merge PR จึงรวมประวัติ main แล้ว revert
`f606045` แบบเก็บ history เพื่อให้ผลสุดท้ายเป็น source tree ของ `29dace8`
บวก CI fix/รายงานนี้เท่านั้น ไม่ reset/force-push และไม่ลบ branch งานเดิม
ตรวจ diff กับ target แล้วอนุญาตให้ต่างได้เฉพาะ browser tests สามไฟล์,
`docs/README.md` และรายงานนี้

เป็น code rollback เท่านั้น ไม่ downgrade/restore ข้อมูล Supabase, ไม่แก้ secrets,
ไม่ Publish Dify และไม่ถือว่าการเปิด PR คือการ merge/deploy สำเร็จ

## สาเหตุและสิ่งที่เปลี่ยน

CI [run 40682897127](https://github.com/IMLV1/SOC/actions/runs/40682897127)
ของ commit `f606045` ผ่าน backend/frontend/prototype แต่ไม่ผ่าน browser suite
tests ยังอ้างข้อความก่อน UX เปลี่ยน ขณะที่ source ของหน้าเว็บใช้ข้อความใหม่แล้ว:

| Test | Selector เดิม | UI ปัจจุบัน |
|---|---|---|
| Magic UI mobile | สร้างบัญชีเพื่อเริ่มเรียน | สมัครเพื่อบันทึกความคืบหน้า |
| Account responsive | ไปหน้ารอบฝึก | เปิดรอบฝึก (แยกจากข้อสอบ) |
| Account responsive | อ่านข้อมูลตัวอย่าง | ดูตัวอย่างก่อน |
| Guest scenarios | ข้อสอบจริงยังไม่เปิด | รายการนี้ไม่ใช่ข้อสอบเลื่อนระดับ |

แก้ selectors ให้ตรง accessible names ปัจจุบัน และเพิ่ม assertions ของ `href`
เป็น `/register`, `/runs`, `/demo` ตามหน้าที่จริง ไม่เปลี่ยน copy/product behavior
guest/session fixtures ทำให้ layout tests ไม่ขึ้นกับบัญชี/บริการจริง
responsive suite abort API ที่ไม่ได้ mock เพื่อไม่ส่งคำขอออกนอก fixture

คงการตรวจ horizontal overflow, button bounds, touch targets, font size,
keyboard/menu navigation, viewport ทั้งห้า, refresh/session redirects และ reduced motion
ไม่มีการเพิ่ม timeout/retry/sleep/skip หรือลด assertions เพื่อให้ CI เขียว

## ผลตรวจ local

Windows, Node `24.20.0`, npm `11.19.0`, dependencies จาก `npm ci` ตาม lockfile
ใช้ production frontend แยกที่ `127.0.0.1:15175`, rewrite backend ไปพอร์ตว่าง `15999`
ไม่เปิด Docker, ไม่ใช้ Supabase/Dify และไม่มี mutation ของบัญชีจริง

- `npm ci`, `npm run lint`, `npm run typecheck`: ผ่าน
- `npm run build`: compile/type/static generation ผ่าน; ครั้งแรก CLI หยุดด้วย
  `SecurityFatalError`/upgrade reminder ของ Next.js `16.4.0`; รันคำสั่งเดิมอีกครั้งแล้ว exit 0
  ไม่มีการปิด security checks หรือเปลี่ยน runtime/package/lockfile
- `node --test tests/assets.test.mjs`: **1 passed**
- `npm run test:e2e -- tests/browser/magic-ui.spec.ts tests/browser/responsive.spec.ts tests/browser/home-design.spec.ts tests/browser/auth-navigation.spec.ts`:
  **19 passed**, ไม่มี retries หรือ skips ในชุดที่เลือก
- viewport account: 320/375/768/1024/1440px; landing: 375/768/1440px

คำเตือน Next.js เป็นประเด็น dependency security ที่ต้องประเมิน upgrade ตาม advisory แยก
ไม่ใช่หลักฐานว่าแก้ช่องโหว่แล้ว และไม่ใช่เหตุผลให้เปลี่ยน pin เป็น latest ในงาน selector นี้

ไม่รัน local PostgreSQL integration ใหม่ในรอบนี้ เพราะไม่แก้ backend/domain/DB
ผล local ไม่แทน GitHub CI ของ SHA หลัง push, branch protection หรือ deployed acceptance
สถานะ ณ เขียนรายงาน: **รอยืนยันบน GitHub**

## Follow-up จาก GitHub run 40776334164

Backend/frontend/prototype ผ่าน แต่ browser suite พบ guest scenarios อ้าง copy เก่าอีกจุด
แก้ให้ตรงข้อความแยก training catalog จากข้อสอบ และเพิ่ม href `/learning`
คง assertions ของ public metadata, viewport ทั้งสาม และ API ปฏิเสธ exam payload (422/404)
ไม่เปลี่ยน application code; GitHub CI ของ commit ถัดไปยังรอยืนยัน