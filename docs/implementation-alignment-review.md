# ตรวจแนวทาง implementation เทียบ docs

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


วันที่ 16 ตุลาคม 2026 — source `bdc4fb0` บน `codex/password-reset-plan`; main ที่ตรวจ CI คือ `e8c77a1` หลัง merge PR #13

## ข้อสรุป

ทิศทางหลักสอดคล้องกับแบบออกแบบ: Next.js App Router/TypeScript, FastAPI/Python, PostgreSQL/SQLAlchemy/asyncpg/Alembic, durable jobs และ evaluator แยก process, approved corpus และ frozen RAG citations อยู่ฝั่ง server ระบบฝึกมี implementation แล้ว แต่ยังไม่ใช่ learning/exam และ production ที่ครบตามเป้าหมายปลายทาง

ปัญหาชัดเจนที่สุดคือเอกสารสถานะปัจจุบันปะปนกับรายงานย้อนหลัง ทำให้เหมือนยังอยู่ข้อ 04 หรือทำข้อ 13 ไม่เสร็จ ทั้งที่โค้ดและ CI ไปไกลกว่านั้น ขณะเดียวกันการ merge โค้ดไม่ใช่หลักฐานว่า Render เปิดทุก feature แล้ว

## วิธีตรวจและขอบเขตความเชื่อมั่น

- สำรวจไฟล์ docs ทั้งชุด: Markdown 36 ไฟล์, JSON artifacts/evidence 13 ไฟล์ และ OpenAPI 1 ไฟล์ ตรวจหัวข้อ/สถานะ/ข้อจำกัดและ local links ทั้งชุด พร้อมอ่านเชิงลึก contract, architecture, checklist, RAG, deployment และรายงานที่เกี่ยวข้อง
- Parse JSON ทุกไฟล์และ OpenAPI; พบ 58 approved operations และ 27 draft operations การ parse ผ่านไม่ใช่การรับรองเนื้อหาทุก claim
- เทียบกับ router registration, dependencies, migrations 18 revisions, CI workflow, training guards, Google UI และ tests ที่มีจริง ไม่ใช่ full security audit หรือการพิสูจน์ correctness ของทุกบรรทัด
- รอบนี้ไม่รัน PostgreSQL/browser/deployment ใหม่ และไม่เรียก provider จริง ใช้ CI ที่ตรวจจาก GitHub ของ SHA ระบุด้านล่างประกอบหลักฐานเดิม

## ข้อพบที่ควรจัดการ

| ลำดับ | ข้อพบ / หลักฐาน | ผลกระทบและงานต่อ |
|---|---|---|
| 1 | [architecture.md](architecture.md) บรรทัด 18 ยังบอก runner/detection ไม่ implement; [api.md](api.md) บรรทัด 380 บอก RAG ยังไม่ติดตั้ง; [database.md](database.md) ส่วน migration ยังบอกไม่มี runs/jobs/events/evaluation | ปรับ status banner และ current implementation matrix ให้ตรงโค้ด แยก design target ออกจาก historical checkpoint โดยไม่ลบหลักฐานเก่า |
| 2 | [steps-11-13-follow-up.md](steps-11-13-follow-up.md) ส่วน 13 ยัง unchecked ทั้งหมดและท้ายไฟล์บอก global controls pending แต่ [checklist](implementation-checklist.md) และรายงานข้อ 12/13 ระบุ local acceptance ผ่าน | ทำเครื่องหมาย superseded/อ้างรายงานใหม่ ไม่ใช้รายการเก่านี้เริ่มทำซ้ำหรือเลือก policy ใหม่ |
| 3 | [step-14-verification.md](step-14-verification.md) บรรทัด 3/76 และ checklist ข้อ 14 ยังรอ commit/PR/GitHub CI ทั้งที่ PR #13 merged และ main CI ผ่านแล้ว | เพิ่ม checkpoint ของ SHA/CI ล่าสุด; อัปเดตเฉพาะช่อง GitHub CI ได้ ไม่ติ๊ก quality acceptance ทั้งข้อ |
| 4 | [render-preview.md](render-preview.md) ยังอ้าง branch ข้อ 12 และ deployed SHAs เก่า | เพิ่ม release record แยก web/API/schema: จากการตรวจในงาน deploy ก่อนหน้า web `b72a549`, API `8c2a978`, Auto-deploy Off ทั้งคู่ และ DB ยังไม่ migrate สำหรับ API รุ่นใหม่ ไม่ใช้ health 200 ยืนยันว่าเป็น backend ล่าสุด |
| 5 | ข้อ 14 ยังขาด independent review, paired answer benchmark release v2 และ unknown usage 6 calls; ดู [รายงาน](step-14-verification.md) และ [ledger](artifacts/step-14-ledger-and-latency.json) | เป็น acceptance gap จริง ไม่ใช่แค่เอกสารเก่า คง overall checkbox ว่าง และ cost_usd=null จนมีหลักฐาน reconcile |
| 6 | [agent review](step-14-agent-review.md) พบ supported 53/57 claims และ 4 claims รองรับไม่ครบ; กลุ่มคำถามไทยมี 10/30 sampled claims เป็นอังกฤษล้วน | เพิ่มการทดสอบ observation/general guidance และภาษา ก่อนเปลี่ยน prompt แล้ววัดผลใหม่; citation ถูกชุดไม่ได้ยืนยัน semantic grounding |
| 7 | ข้อ 15–17 ยัง draft; router จริงไม่มี learning/attempt/grading routes และ learner scoring ยัง N/A | ตรงลำดับแผน แต่เป้าหมายเรียน → สอบ → feedback → retake/unlock ยังไม่เกิดจริง ต้องตัดสิน rubric/retake/override ก่อนเปิด |
| 8 | Render เป็น auth-only preview ไม่มี runner ต่อเนื่อง; CI/CD ข้อ 18–19, restore drill, release digests และ enforced branch protection ยังไม่มีหลักฐานรับครบ | คง preview label และ disabled run controls แยก CI success ออกจาก operational/production acceptance |
| 9 | [password-reset-plan.md](password-reset-plan.md) เป็น draft และ Google real linking/session ยังมีข้อจำกัดใน [คู่มือ](google-login-setup.md) | ไม่แสดงว่ากู้รหัสผ่านหรือ Google บน Render พร้อมแล้ว ต้องเลือก email provider/policy/environment ก่อน implementation/real delivery |

รายงานสถานะเก่าที่ระบุวันที่หรือขอบเขตชัดสามารถเก็บไว้ได้ ปัญหาคือการใช้ข้อความเหล่านั้นเป็นสถานะล่าสุดโดยไม่มีลิงก์ไป checkpoint ปัจจุบัน

## สิ่งที่สอดคล้องกับแผนจากหลักฐานที่ตรวจ

- FastAPI register routers ของ auth, runs, investigation, analysis, knowledge และ evaluation; Next.js ใช้ typed API client และ Google unavailable fallback สำหรับ API รุ่นเก่า
- Dependency pins/lockfiles และ migration wrapper มีอยู่; CI ใช้ frozen dependencies, unit/contract, generated client, production build/assets guard และ disposable integration stack
- CI gate ใช้ผลทุก required job ไม่ได้ให้ failure กลายเป็น success แต่การมี gate ไม่พิสูจน์ branch protection
- Training creation ใช้ training catalog; question routes ตรวจ training identity และ mutable state ไม่มีการเปิด exam endpoint เพื่ออาศัย training serializer
- Tests ครอบคลุม pause/release contention, lease fencing, cross-run citations, revocation, retry snapshots, finish/question race และ unknown component reconciliation; ไม่พบ localStorage, dangerouslySetInnerHTML หรือ FastAPI BackgroundTasks ใน source frontend/src และ backend/app จากการค้นรอบนี้
- ข้อ 12 มี bounded real C แยก operator; C unavailable บน public UI ไม่ขัดกับการมี operator experiment จริง
- ไม่ใช้ผล agent review แทน independent human acceptance; artifacts ยังคง human_approved=false และค่า cost ที่ไม่ทราบเป็น null

## ผลตรวจรอบนี้

| Check | ผล |
|---|---|
| Backend pytest -m 'not integration' -q | 76 passed, 77 deselected |
| Local Markdown links | ผ่าน |
| Generated TypeScript API types --check | ผ่าน |
| JSON/OpenAPI parse | ผ่าน; approved 58 / draft 27 operations |
| [main CI e8c77a1](https://github.com/IMLV1/SOC/actions/runs/38881005698) | prototype/backend/frontend/integration/ci-gate success ครบ 5 งาน |
| [PR #14 CI bdc4fb0](https://github.com/IMLV1/SOC/actions/runs/38882209078) | success ครบ 5 งาน |

ผล CI เป็น snapshot ตอนตรวจ ไม่ใช่การรับรองทุก future commit หรือการทดสอบ public Render รอบใหม่

## ลำดับงานที่แนะนำ

1. รวม current status/หลักฐาน CI/deploy ให้ตรงกันก่อน โดยเก็บ historical reports และไม่แก้ผล benchmark เก่า
2. ปิด acceptance ข้อ 14: ตรวจ labels/claims อิสระ → paired v2 benchmark ภายใต้สิทธิ์และงบเดิม → reconcile usage จาก provider evidence ที่ยืนยันได้
3. ทำข้อ 15 แล้ว 16–17 ตาม policy ที่ผู้ใช้อนุมัติ โดยคง exam boundary และไม่เปลี่ยน learner score เป็นตัวเลขที่แต่งขึ้น
4. ก่อนเปิดระบบเต็มบน public URL ต้องมี worker/evaluator, pgvector/migration, secrets และ backup/restore ที่ตรวจจริงตามข้อ 18–19
5. ระบบลืมรหัสผ่านเป็น backlog เพิ่มแยกจากการรับรอง core training/RAG; ไม่ให้การทำ auth เพิ่มเลื่อนความหมายของ checklist เดิม

รอบนี้เป็น audit และรายงาน ไม่มีการแก้ policy/โค้ด runtime, ติ๊ก acceptance ทั้งข้อ, merge หรือ deploy เพิ่ม
