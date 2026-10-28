# แก้ปุ่มเริ่มรอบฝึกแล้ว error หาย

ตรวจวันที่ 21 ต.ค. 2026 บนฐาน `a1fc962` และ working tree ของการแก้นี้

## สาเหตุที่ยืนยันได้

`/runs` ใช้ state `message` ร่วมกันระหว่างการเริ่มรอบกับการโหลดรายการ
เมื่อ POST `/runs` ล้มเหลว จะตั้งข้อความ error แล้วเรียก `load()`
พอ GET รายการสำเร็จ `load()` ล้างข้อความ ทำให้ผู้ใช้เห็นว่ากดแล้วเงียบ
browser regression จำลอง 409/429 แล้วพบข้อความหายหลังโหลดรายการรอบที่สองก่อนแก้

ยังไม่ยืนยัน error code ของบัญชีผู้ใช้จริง ไม่อ่านหรือแก้ PostgreSQL ในงานนี้

## การแก้

- แยก `startError`/`startErrorCode` จากข้อความโหลดรายการ การ refresh ไม่ล้างเหตุผลที่เริ่มไม่ได้
- แยกคำอธิบายรอบหรือข้อสอบค้าง, idempotency conflict, session หมดอายุ, โควตา และระบบไม่พร้อม
- เพิ่มลิงก์ตรวจสถานะข้อสอบ/เข้าสู่ระบบ และทางไป JSON practice โดยไม่ข้าม gate
- ระบุว่ารอบจริงต้องใช้ API/ฐานข้อมูล/runner และ AI mock จำลองคำวิเคราะห์ ไม่ใช่ตัวสร้าง log
- เมื่อไม่มี catalog แสดงชื่อปุ่มอธิบายเหตุผล ไม่ปล่อยปุ่มเทาโดยไม่มีบริบท
- กันกดเริ่มระหว่าง loading/busy ไม่เปลี่ยน API, quota, ownership หรือกติกาหนึ่ง running run

## ผล local

- Playwright: `run-start-feedback.spec.ts` + `curriculum-preview.spec.ts`: **10 passed**
  ครอบคลุม 401/409/429/503, error ไม่หายหลัง refresh, catalog ว่าง และ navigation เมื่อ mocked start สำเร็จ
- ทุก API ใน tests ใช้ mock/block ไม่สร้างบัญชีหรือ run ในฐานข้อมูลจริง
- `npm run lint` และ production `npm run build` รวม TypeScript: ผ่านใน container แยก ปิด network
- `node --test tests/assets.test.mjs` หลัง build: **1 passed**
- `git diff --check`: ผ่าน
- Dev container ต้อง restart เฉพาะ frontend เพื่อรับไฟล์ที่ bind mount เปลี่ยน ก่อน browser tests รอบสุดท้าย

GitHub CI ของการแก้นี้ยังรอยืนยัน ไม่ได้ทดสอบว่าบัญชีผู้ใช้จริงเริ่ม runner สำเร็จ
หลัง refresh หน้าและกดเริ่มอีกครั้ง ข้อความที่คงอยู่จะระบุเงื่อนไขที่ต้องแก้ต่อ
ไม่มี migration/seed/provision, ไม่มีการแก้หรือล้าง PostgreSQL และไม่เรียก provider จริง
