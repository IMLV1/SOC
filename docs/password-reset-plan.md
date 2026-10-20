# แผนระบบลืมรหัสผ่านทางอีเมล

สถานะ: **Draft / ยังไม่ได้ implement หรือ deploy** — 16 ตุลาคม 2026

เอกสารนี้เป็นแผนงาน ยังใช้รีเซ็ตรหัสผ่านไม่ได้ และไม่ได้เปลี่ยนสัญญา API ที่อนุมัติหรือผลตรวจ checklist

## เป้าหมายและสถานะปัจจุบัน

ให้เจ้าของบัญชีตั้งรหัสผ่านใหม่ผ่านลิงก์ที่ส่งไปอีเมลเดิม โดยคง user ID, role, quota, run, assessment, note, progression และประวัติเดิม ไม่สร้างบัญชีซ้ำหรือเปลี่ยนอีเมลระหว่าง reset

ปัจจุบันระบบมี password login และ Google OAuth implementation แต่ยังไม่มี forgot/reset password endpoints หรือบริการส่งอีเมลสำหรับ flow นี้ บน Render preview Google login ยังไม่เปิดใช้ การมีเอกสารนี้ไม่ได้ทำให้ feature พร้อมใช้งาน

นโยบาย Google เดิมยังคงเดิม: อีเมลตรงกันไม่ auto-link; บัญชี SOC เดิมต้องยืนยันรหัสผ่านและเชื่อม Google ก่อนใช้งาน identity เดิม ดู [Google login setup](google-login-setup.md) การ reset ไม่ใช่การผูก Google และไม่ bypass นโยบายนี้

## Flow ที่เสนอ

1. หน้า login มี “ลืมรหัสผ่าน” ไปหน้ากรอกอีเมล แสดง loading/error และผลตอบรับกลางที่ไม่บอกว่ามีบัญชีหรือไม่
2. API ตรวจ input, Origin/CSRF และ rate limit แล้วตอบข้อความเดียวกัน เช่น “หากอีเมลนี้มีบัญชีที่รองรับ ระบบจะส่งลิงก์ตั้งรหัสผ่านให้” โดยไม่เปิดเผย account status หรือ Google identity
3. สำหรับบัญชีที่เข้าเกณฑ์ สร้าง opaque token แบบสุ่มที่เดาไม่ได้ เก็บเฉพาะ hash และสร้าง durable email job ใน transaction เดียวกัน
4. ผู้ใช้เปิดลิงก์จากอีเมลและกรอกรหัสใหม่พร้อมยืนยัน การเปิดลิงก์ด้วย GET ยังไม่ consume token เพื่อรองรับ email link scanners
5. การยืนยันด้วย POST ตรวจ token/expiry/สถานะบัญชี แล้วอัปเดต password hash, consume token, revoke reset tokens ที่เหลือและ session เดิมแบบ atomic พร้อม audit ตาม policy ที่อนุมัติ
6. สำเร็จแล้วกลับหน้า login ไม่ auto-login ไม่ย้ายประวัติหรือเปลี่ยนสิทธิ์ ถ้า token ใช้แล้ว/หมดอายุ/ผิด ให้ข้อความกลางและทางขอลิงก์ใหม่

## API/UI ที่เสนอ — ทั้งหมดยัง draft

| Requirement | Endpoint / UI ที่เสนอ | พฤติกรรมสำคัญ |
|---|---|---|
| PR-01 ขอรีเซ็ต | POST /api/v1/auth/password-reset/request | body มี email; 202 แบบกลาง; rate limit 429 ไม่ขึ้นกับว่ามีบัญชี |
| PR-02 ยืนยันรีเซ็ต | POST /api/v1/auth/password-reset/confirm | body มี token/password; consume ครั้งเดียว; ไม่คืน session/token |
| PR-03 เริ่ม flow | /forgot-password | label, loading, retry, ข้อความกลาง และ link กลับ login |
| PR-04 ตั้งรหัสใหม่ | /reset-password | validate password, expired/used/error/success; token อยู่ใน memory ระหว่างส่ง |
| PR-05 ส่งอีเมล | Python worker + email adapter | durable jobs, timeout, bounded retry, sanitized logs และ delivery status |
| PR-06 ตรวจสอบย้อนหลัง | server audit | request/consume/revoke/delivery outcome แบบไม่เก็บ token/password |

ชื่อ endpoint, response/error schema และ semantics ต้องบันทึกใน SRS/OpenAPI และตรวจ framework-generated OpenAPI ก่อนเปิด route จริง FastAPI เป็นเจ้าของ auth ผ่าน same-origin proxy ของ Next.js ตามระบบเดิม

## Storage, concurrency และ secrets

- เพิ่ม Alembic revision ใหม่หลังตรวจ migration graph ห้ามแก้ revision ที่ใช้งานแล้ว เสนอ token table ที่มี user_id, token_hash แบบ unique, created_at, expires_at, consumed_at และ revoked_at พร้อม index/retention ที่เหมาะสม
- ยึดลำดับ lock ใน SRS โดยออกแบบ user auth guard → reset token/resource → session revocation/audit/job writes ให้ทุก operation ที่แตะรายการเดียวกันใช้ลำดับคงที่ ตรวจความเข้ากันได้กับ login/link/logout และ password verification ที่อาจกำลังทำงานอยู่ ไม่ถือ transaction ระหว่างเรียกผู้ให้บริการอีเมล
- Parallel confirm ต้องสำเร็จได้ครั้งเดียว; login หรือ OAuth ที่เริ่มก่อน reset ต้องไม่สร้าง session จาก credential/auth state เก่าหลัง reset สำเร็จ อาจต้องมี auth generation guard ตามการออกแบบจริง
- Token ที่ต้องส่งในอีเมลห้ามเก็บ plaintext ใน token table, job payload หรือ audit หาก durable outbox ต้องเก็บลิงก์ ให้เข้ารหัสด้วย runtime key แยกจาก DB จำกัดสิทธิ์ decrypt เฉพาะ mail worker และล้าง payload ตาม retention ที่อนุมัติ
- Retry delivery อาจส่งอีเมลซ้ำได้ ใช้ job dedupe และ provider idempotency เมื่อรองรับ ไม่อ้าง exactly-once delivery และไม่สร้าง token ใหม่ทุก retry
- Mail credentials/encryption key อยู่ใน runtime secret store หรือ ignored local file ไม่อยู่ใน Git, image, NEXT_PUBLIC, browser bundle หรือ CI artifacts; .env.example ใส่ชื่อ config และค่าว่างเท่านั้น

## ข้อกำหนดความปลอดภัยและ UI

- ใช้ password hashing/policy เดิม ไม่ส่งรหัสผ่านทางอีเมล และไม่ให้ผู้ดูแลอ่านรหัสเดิม
- Request response/status และ timing ไม่ควรแยกบัญชีมีจริง/ไม่มีจริง/disabled/Google-only; rate limit ตาม IP และ normalized email พร้อมเพดานรวม ป้องกันการใช้ระบบส่งอีเมลรบกวนผู้อื่น
- Reset URL ใช้ canonical origin จาก server config ที่อนุมัติ ไม่สร้างจาก Host หรือ redirect URL ของผู้ใช้ ใช้ HTTPS ภายนอกและ loopback HTTP เฉพาะ local
- เลือกวิธีส่ง token ในลิงก์ที่ไม่ให้รั่วผ่าน access logs/Referer; ข้อเสนอคือ URL fragment แล้วล้างจาก address bar ก่อนส่ง POST ห้าม analytics/third-party resources บนหน้า reset และตั้ง Referrer-Policy: no-referrer, Cache-Control: no-store ตรวจทั้ง browser/proxy/provider logs
- ไม่ใช้ localStorage/sessionStorage เก็บ token/password ไม่สะท้อน token ใน error, screenshot, tracing หรือ test artifacts
- บัญชี disabled ต้องไม่ถูกเปิดใหม่ด้วย reset ส่วน Google-only account และการ revoke OAuth flows ที่ค้างอยู่ต้องตัดสินใจตามหัวข้อด้านล่าง
- UI รองรับ keyboard/focus, labels, password manager และหน้าจอ 375/768/1440; เมื่อ mail service ปิด ให้แสดงว่า feature unavailable ไม่แสดงว่าส่งสำเร็จจริง

## สิ่งที่ต้องตัดสินใจก่อน implementation/เปิดใช้จริง

- [ ] Email provider/SMTP, sender domain/address, domain verification และ environment ที่ใช้งาน รวม free tier, งบและเพดานส่ง ยังไม่มีการเลือกหรืออนุญาตบริการเสียเงิน
- [ ] อายุ token, จำนวนคำขอต่อช่วงเวลา, resend cooldown, daily cap และ retention; เอกสารนี้ยังไม่กำหนดตัวเลขเป็น policy
- [ ] การออก token ใหม่ revoke token เดิมทันทีหรืออนุญาตหลาย token ภายใต้เพดาน และการแจ้งเตือนเมื่อ password เปลี่ยน
- [ ] ยืนยัน policy revoke session ทุกเครื่อง, pending OAuth/login flows และพฤติกรรม concurrent login หลัง reset
- [ ] Google-only account จะตั้ง password ครั้งแรกผ่าน flow นี้ได้หรือไม่; ห้ามเลือกแทนผู้ใช้เพราะเพิ่มวิธีเข้าถึงบัญชี
- [ ] ขั้นตอน support recovery เมื่อเข้าอีเมลไม่ได้ ใครมีสิทธิ์ดำเนินการและต้องตรวจตัวตนอย่างไร; ไม่เพิ่ม admin bypass หรือ auto-link จากอีเมลตรงกัน
- [ ] อนุมัติการใช้ real recipient/test mailbox และ provider credentials ก่อนส่งอีเมลจริง ไม่ใช้คำขอสร้างเอกสารนี้เป็นสิทธิ์ส่งอีเมลหรือ deploy

## แผนทำงานและเกณฑ์รับงาน

1. สรุป policy ที่ค้าง แล้วเพิ่ม requirement/contract/config และ migration พร้อม least-privilege grants
2. ทำ email adapter แบบ fake สำหรับ CI และ durable worker job พร้อม outbox encryption/retry/retention; CI ต้องไม่ส่งอีเมลจริง
3. ทำ request/confirm และ frontend ทั้งสองหน้า พร้อม regression tests ใน CI เดิม
4. ทดสอบ PostgreSQL จริง: token hash-only, expired/used/revoked token, parallel confirm, request/confirm race, failed transaction rollback, session revocation และ concurrent login/OAuth fencing
5. ทดสอบ account enumeration, Origin/CSRF, rate limit, canonical origin, disabled/unknown/Google-only policy, provider outage/timeout/duplicate jobs และความลับไม่หลุดใน logs/browser/assets/artifacts
6. E2E ใช้ fake mailbox: request → เปิดลิงก์ → reset → login ด้วยรหัสใหม่; รหัสเก่าและ session ที่ revoke ใช้ไม่ได้ ประวัติ/ownership/role/quota เดิมไม่เปลี่ยน ตรวจ responsive และ scanner GET ไม่ consume token
7. เมื่อมี environment/สิทธิ์พร้อม ทำ bounded real-email smoke แยกหลักฐานจาก fake tests ก่อน deploy ตรวจ worker ที่ส่ง mail ได้จริง เพราะ Render Free preview ปัจจุบันไม่มี background worker ต่อเนื่อง

เกณฑ์ผ่าน: contract/schema checks และ regression tests ผ่านจริง, recovery ใช้งานได้ครบโดยไม่เปิดทางข้ามสิทธิ์, มี delivery/retention/secret configuration ที่ยืนยันแล้ว และรายงานข้อจำกัดตามจริง ก่อนถึงจุดนั้นยังไม่ติ๊ก checklist ว่า feature เสร็จ
