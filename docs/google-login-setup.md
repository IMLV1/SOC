# Google login สำหรับ SOC local

## Supabase Google Auth — ใช้ส่วนนี้สำหรับ environment 22 ต.ค. 2026

ส่วนหลังเส้นคั่นเป็นคู่มือ direct Google OAuth เก่า ไม่ใช่ config ของ stack Supabase ใหม่นี้
สถานะจริง: [Supabase verification](supabase-verification.md); provider ยังปิดจนผู้ใช้ตั้งค่า Dashboard

### 1. Google Cloud

เปิด [Google Cloud Console](https://console.cloud.google.com/), เลือก project เดิมหรือสร้าง SOC ใหม่
เข้า Google Auth Platform → Branding/Get started ใส่ชื่อ Sentinel SOC และอีเมลติดต่อ
Audience เลือก External; ระหว่างทดสอบเพิ่มบัญชี Google ของตน/เพื่อนใน Test users ตามที่ console รองรับ
Data Access ใช้เฉพาะ openid/email/profile ไม่เปิด Gmail/Drive permissions หรือบริการที่มีค่าใช้จ่าย

### 2. สร้าง Web client

Google Auth Platform → Clients → Create client → Web application
ตั้งชื่อ SOC Supabase Web; ใส่ค่าต่อไปนี้ให้ตรงช่อง ไม่สลับ Google callback กับ callback ของเว็บ

| ช่อง | ค่า environment นี้ |
|---|---|
| Authorized JavaScript origins | `http://127.0.0.1:4175` |
| Authorized redirect URIs | `https://bcehkugtxgatdgesvowc.supabase.co/auth/v1/callback` |

กด Create แล้วเก็บ Client ID/Secret ไว้ส่วนตัว ไม่ส่ง Secret ในแชต/ใส่ repository/frontend
อย่าใช้ callback 13014/direct Google ของ Windows ในบันทึกเก่าด้านล่างแทน Supabase callback

### 3. Supabase Google provider

ใน project นี้เข้า Authentication → Sign In / Providers (บางหน้าชื่อ Providers) → Google
เปิด provider ใส่ Client ID/Client Secret ที่สร้าง แล้ว Save
ไม่เปิด Skip nonce checks/Allow users without email เพื่อหลบ validation

### 4. Supabase URL Configuration

Authentication → URL Configuration:

- Site URL: `http://127.0.0.1:4175`
- Redirect URLs: เพิ่ม `http://127.0.0.1:4175/api/v1/auth/google/callback`
- ถ้าต้องการให้ลิงก์ยืนยันอีเมลกลับหน้า login ให้เพิ่ม `http://127.0.0.1:4175/login` ตาม email configuration

ช่วง local นี้ให้เปิดเว็บด้วย **127.0.0.1** ตาม callback ที่ตั้ง ไม่สลับเป็น localhost
เพราะ binding cookie เป็น host-specific เมื่อ deploy จึงค่อยเพิ่ม HTTPS origin/redirect จริงแบบ exact
ไม่ใช้ wildcard กว้าง ๆ หรือ port ของ Supabase CLI local เพราะ environment นี้ใช้ managed project

### 5. ทดสอบ

เปิด `http://127.0.0.1:4175/login`, reload หน้าแล้วปุ่ม Google จะแสดงเมื่อ Auth settings available=true
กด → Google consent → Supabase → same-origin callback → account
ตรวจ refresh/logout/relogin และ quota 10/20; ผู้สมัครใหม่ยังเป็น Analyst ไม่เลือก role จาก Google metadata
ไม่ต้องสมัครด้วย password ก่อนสำหรับบัญชี Google ใหม่ แต่ระบบไม่รวมประวัติของบัญชี local เก่าเอง

หาก redirect_uri_mismatch ให้เทียบ callback ของ Google กับ Supabase ให้ตรงทั้ง scheme/host/path
หากเข้าทดสอบไม่ได้ ตรวจ Audience/Test users และ provider Save ก่อน ไม่แก้โดยปิด PKCE/CSRF/TLS
เมื่อทำเสร็จแจ้งว่า “ตั้ง Google แล้ว” เพื่อทดสอบ availability/callback ต่อ โดยไม่ส่ง Secret

อ้างอิง [Supabase Google Auth](https://supabase.com/docs/guides/auth/social-login/auth-google)
และ [Google Web OAuth](https://developers.google.com/identity/protocols/oauth2/web-server)

---

## บันทึก direct Google OAuth เดิม (ประวัติ ไม่ใช่ Supabase runtime config)

> **หมายเหตุสถานะปัจจุบัน:** การกล่าวถึง Gemini ในเอกสารนี้เป็นข้อมูลย้อนหลัง/หลักฐานของ implementation ก่อนเลือก Dify ไม่ใช่คำสั่งให้เปิดใช้หรือสถานะ provider ปัจจุบัน; repository ต้องใช้ Dify API เท่านั้น และ runtime ยังปิดจน integration ผ่านการตรวจรับ

คู่มือนี้อธิบายการเชื่อม Google login สำหรับ local. โค้ด migration/API/UI มีแล้ว แต่การทดสอบในเครื่องไม่เท่ากับเปิดใช้กับผู้ใช้จริง. ค่าเริ่มต้นปิด และไม่ deploy หรือเปิด billing จากเอกสารนี้

## นโยบายที่ผู้ใช้ยืนยัน 16 ต.ค. 2026

- Google identity ใหม่: สร้าง Analyst พร้อม quota 10 training runs/20 logical AI requests ต่อวัน UTC และ login ทันที เป็นข้อยกเว้นของ password registration ที่ยังไม่ auto-login
- อีเมลตรง SOC user เดิม: ไม่ auto-merge ต้อง password login แล้วกรอกรหัสผ่านอีกครั้งที่หน้าบัญชีเพื่อเชื่อม Google อีเมลเดียวกันครั้งแรก จากนั้นกด Google เข้า user ID เดิมได้
- ผูกด้วย Google issuer/sub ซึ่งคงที่ ไม่ใช้ email เป็น identity key เมื่ออีเมล Google เปลี่ยน ยังเข้า user เดิม แต่ไม่เปลี่ยน SOC email/owner/role/quota อัตโนมัติ
- Google-only user ไม่มี password ไม่สร้าง password สมมติ และ password login จะล้มเหลวแบบ generic ยังไม่มี unlink/เปลี่ยน identity/password enrollment/reset password ในขอบเขตนี้
- หนึ่ง Google identity ต่อ user และหนึ่ง user ต่อ identity บัญชี disabled เข้าไม่ได้ ไม่ยกระดับเป็น Instructor จาก email/domain/Google claims

SOC password registration ยังไม่ verify email การเอา email ที่กรอกเองมาตรงกันจึงไม่พิสูจน์สิทธิ์เข้าประวัติเดิม ดู [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect)

## Client ที่สร้างจริง

ผู้ใช้อนุญาต Cloud Terms, Google API Services User Data Policy และการสร้าง credential ณ ขั้นตอนนั้นแล้ว สร้าง project `SOC Local Login` (`soc-local-login`), แอป `SOC Learning Lab (Local)` External/Testing และ Web client `SOC Local Web 13014` สำเร็จ ตรวจจากรายการ Clients และ metadata JSON ที่ดาวน์โหลด ไม่เปิด billing และไม่กด Start free

Authorized redirect URI: `http://127.0.0.1:13014/api/v1/auth/google/callback`

OAuth Client ใช้เฉพาะ OpenID/email/profile และแยกจาก Dify app key ไม่ขอ offline access/refresh token Client secret เก็บเฉพาะ `C:\Users\GOODK\SOC\.local\secrets\google_oauth_client_secret.txt` (ตัว secret ไม่ใช่ JSON) และ runtime metadata ที่ `.local/secrets/google_oauth_config.json` ทั้งสองไฟล์ถูก Git exclude แล้ว ห้ามส่ง secret ลงแชต/commit/frontend/log Downloaded JSON ใน Downloads เป็น credential ส่วนตัวเช่นกัน ไม่ใช้ใน build context

[คู่มือ Web Server OAuth ของ Google](https://developers.google.com/identity/protocols/oauth2/web-server) URI ต้องตรง scheme/host/port/path; localhost กับ 127.0.0.1 เป็นคนละ URI Local นี้ให้ใช้ 127.0.0.1 เท่านั้น

## Requirement-to-endpoint mapping

| Requirement | Endpoint | Contract |
|---|---|---|
| FR-001 availability | GET `/api/v1/auth/google/status` | available และ linked ของ session ปัจจุบันเท่านั้น |
| FR-001 Google login/link | POST `/api/v1/auth/google/start` | JSON, Origin/CSRF, rate limit; purpose=link ต้อง password reauthentication |
| FR-001 callback | GET `/api/v1/auth/google/callback` | single-use state/browser/session binding, 303 ไป fixed local destination |

OpenAPI และ generated TypeScript DTOs ตรวจเทียบ FastAPI เช่นเดียวกับ routes เดิม ไม่มี Google token/secret ใน DTO Callback ไม่ใช่ generic GET mutation: ใช้ authorization response state + HttpOnly binding cookie ที่ออกจาก CSRF-protected POST และตรวจ nonce/PKCE ก่อนออก session

## Database และ security boundary

Migration ใหม่ `0018_google_login` เพิ่ม unique issuer/sub และหนึ่ง identity ต่อ user พร้อม five-minute flow: state/binding/nonce/session เก็บ hash; PKCE verifier อยู่ server DB ชั่วคราวและลบทิ้งเมื่อ consume Password hash nullable รองรับ Google-only signup ไม่แก้ migrations เดิม

API runtime มีสิทธิ์ auth tables ใหม่ worker/evaluator ไม่มีสิทธิ์ Retention role ลบ expired flows ได้; scheduler ยังไม่ implement เช่นเดียวกับ auth challenges เดิม

Consume flow commit ก่อน Google network; denied/invalid/provider timeout replay ไม่ได้ Provider กลับมาแล้วต้องตรวจ flow expiry และ active link session ซ้ำ Identity decision ใช้ dedicated transaction advisory guard ก่อน user/session; unique constraints กัน duplicate subject/user และ password registration race ไม่ถือ DB transaction รอ Google

Success rotate/revoke session เดิม ใช้ opaque SOC session + CSRF เดิม Google tokens ไม่บันทึก/return browser Cookies HttpOnly/SameSite=Lax และ Secure ตาม environment Callback แสดงเฉพาะ fixed safe status: `/login?google=failed`, `link_required`, `/account?google=success` ไม่ echo code/state/error_description ไม่มี open redirect และตั้ง Referrer-Policy=no-referrer

Docker API ใช้ `--no-access-log` เพื่อไม่เก็บ callback query เมื่อรัน Uvicorn เองต้องใช้ flag เดียวกัน proxy/logging ภายนอกต้องไม่บันทึก callback query เช่นกัน ไม่เปิด debug network/JWT logs

## Config และการเปิด local

```text
GOOGLE_OAUTH_ENABLED=false
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET_FILE=
GOOGLE_OAUTH_REDIRECT_URI=
```

config ต้องเป็น HTTPS หรือ loopback HTTP origin อยู่ใน AUTH_ORIGINS, path ต้องตรง callback, ไม่รับ query/fragment/userinfo ผิด config fail closed และ status ไม่อ้าง available

ใช้ `.local/start-step14-local.ps1` กับ `.local/compose.google.yaml` ที่เตรียมส่วนตัว Runtime secret mount read-only เฉพาะ API ไม่มี secret ใน image/build args/frontend/environment value ไม่เพิ่ม credential เป็น mandatory secret ของ Compose/CI CI กำหนด Google disabled และทดสอบ exchange fake เท่านั้น ไม่เรียก Google

Local web: http://127.0.0.1:13014/login บัญชีเดิม password login → หน้าบัญชี → ยืนยันรหัสผ่าน SOC → เชื่อม Google; บัญชีใหม่กด Google จากหน้า login ได้เลย Google consent/Testing ของ project อาจจำกัดบัญชีที่เลือก เมื่อ provider ปฏิเสธยัง login รหัสผ่านได้ตามเดิม

Pinned transport: google-auth[requests]==2.62.0, requests==2.34.2, transitive pins ใน uv.lock ตรวจ signature/issuer/audience/expiry ด้วย google-auth และตรวจ nonce/azp/sub/verified email ซ้ำ UI แสดง availability/loading/denied/error/linked จริง

## ผลตรวจ

- Offline adapter 15 tests: generated RSA keys/fake cert response, invalid signature/issuer/audience/azp/expiry/nonce/email/config และ sanitized transport errors ไม่มี Google network
- PostgreSQL OAuth 12 tests และ password auth เดิม 9 tests ผ่าน: signup quota, email collision, explicit password linking, owner เดิม, rotation, replay, expired/browser/session binding, denied/provider failure, disabled/revoked session และ concurrent same subject
- Backend non-integration 76 tests ผ่าน; Ruff/strict mypy 73 modules และ frontend lint/typecheck ผ่าน
- Real OAuth local: เลือกบัญชีที่อนุมัติและยอมรับ basic profile/email consent แล้ว Google token exchange + signature/nonce/PKCE validation ผ่านจริง ระบบพบ email collision จึง redirect `link_required` และไม่ออก session/auto-merge ตาม policy บัญชีเดิมยังต้อง password login และ explicit link เพื่อยืนยัน real session login จนครบ
- Local frontend/API/worker/evaluator healthy; Google status available=true ผ่าน same-origin proxy API/frontend logs หลัง callback ไม่มี client secret หรือ callback query ตรวจด้วย secret จริงและไม่พิมพ์ค่า ไม่พบ secret จริงใน 22 browser JS assets และ tracked diff
- Compose local CI รอบสุดท้าย exit 0: PostgreSQL integration 77 passed; HTTP smoke 3 passed; browser 15 passed/1 skipped (preview-only ตาม config) รวม Google UI ที่ 375/768/1440px ตรวจ migration/readiness และ worker/evaluator health ผ่าน ยังไม่รัน GitHub CI ของ commit นี้ และยังไม่ถือว่า real Google session login ผ่าน
- รอบ CI ระหว่างตรวจพบ stale schema table expectation (แก้ตาม migration ใหม่) และ local KB_ENABLED=true รั่วเข้าชุด browser ที่ยังไม่มี published corpus (CI baseline ปิด KB ชัดเจน; RAG integration tests เตรียม fake corpus ของตนเอง) บันทึก failure ตามจริง ไม่เพิ่ม timeout/skip tests เพื่อกลบ
