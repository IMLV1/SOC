# Frontend responsive verification — 2026-10-16

ตรวจใน worktree `codex/step-14-rag` บน local http://127.0.0.1:13014 ไม่ deploy ภายนอกและยังไม่รัน GitHub CI ของงานนี้

## ปัญหาและการแก้

- ตรวจบัญชีจริงใน browser ที่ 375px: ลิงก์เมนูสูง 21px, ปุ่ม logout 38px และ input font 14.08px เปลี่ยนเป็น collapsible navigation ที่ <=760px; visible navigation targets >=44px, input font >=16px บนจอ <=900px
- Navigation ใช้ disclosure button พร้อม aria-expanded/aria-controls, keyboard Enter และปิดหลังเลือก link หรือ logout ใช้ DOM links ชุดเดียว ไม่เปลี่ยน auth/session/API
- Grid ใช้ minmax(0,1fr), long-content wrapping; account cards เรียงคอลัมน์เดียวที่ <=900px, profile label/value แยกบรรทัดบนมือถือ และ action buttons wrap ตามพื้นที่
- Auth form คอลัมน์เดียวบน tablet/mobile, controls >=48px บนมือถือ; เว้นระยะ password reauthentication กับ Google button
- ปรับ event filters, run actions, evidence layout และ summaries ให้ shrink/wrap โดยไม่ซ่อน overflow ของทั้งหน้า

## ผลตรวจที่ผ่าน

- `npm --prefix frontend run lint` และ `npm --prefix frontend run typecheck`
- Production frontend Docker build/readiness ผ่าน โดยอัปเดตเฉพาะ frontend ไม่แตะฐานข้อมูลหรือ API
- HTTP smoke: 3 passed
- `SOC_SMOKE_ORIGIN=http://127.0.0.1:13014 npm --prefix frontend run test:e2e`: 20 passed, 1 skipped (auth-only preview ตาม config)
- `responsive.spec.ts`: 320/375/768/1024/1440px ครอบคลุม account ชื่อ/อีเมลยาว, ปุ่มอยู่ใน viewport, mobile menu/touch target, keyboard navigation, input font และไม่มี horizontal overflow ของ account/home/login/register Screenshots ใช้ข้อมูลบัญชีจำลองเท่านั้น
- ตรวจ UI บัญชีจริงที่ 375px ผ่าน browser: visible nav targets 44–49px, input font 16px, horizontal overflow=false

ภาพ layout อยู่ frontend/test-results/responsive-*/account-*.png (ignored test artifacts) ไม่อ้างว่าจำลอง Playwright เทียบเท่าการตรวจ physical iPhone/Android ทุกเครื่อง การเปลี่ยนนี้ไม่ใช่หลักฐานว่า real Google account linking/session login ผ่านครบแล้ว
