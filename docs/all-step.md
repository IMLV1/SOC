# คู่มือรวมข้อ 01–19 ของโครงการ SOC

เอกสารนี้รวบรวมใจความของรายงานตรวจข้อ 01–19 ให้อ่านต่อเนื่องในไฟล์เดียว อธิบายศัพท์และเหตุผลของแต่ละขั้น พร้อมชี้ว่าหลักฐานใดรองรับข้อสรุปและอะไรยังไม่ยืนยัน ผู้อ่านไม่จำเป็นต้องรู้ระบบ SOC หรือศัพท์ backend มาก่อน

> **สำคัญ: นี่เป็นคู่มือสรุป ไม่ใช่หลักฐานตรวจรับฉบับใหม่** รายงานย่อยแต่ละไฟล์บันทึกคนละวัน, branch, commit และสภาพแวดล้อม ตัวเลขทดสอบในเอกสารนี้จึงเป็นผลตามวันที่ในรายงาน ไม่ได้หมายความว่าโค้ดล่าสุดเพิ่งผ่านการทดสอบทั้งหมด และไม่ยืนยันว่า deploy แล้ว ให้ดู [implementation checklist](implementation-checklist.md) และรายงานของขั้นที่สนใจเพื่ออ่านวันที่/รายละเอียดฉบับเต็ม

> **สถานะ AI/RAG ปัจจุบัน:** รายงานข้อ 10–14 บางส่วนบันทึกการทดลอง Gemini และ RAG ภายในในอดีต ซึ่งเป็นหลักฐานทางประวัติศาสตร์ตามขอบเขตที่อนุมัติในเวลานั้น ปัจจุบันทิศทางที่ผู้ใช้ยืนยันคือเรียก **Dify ผ่าน API เท่านั้น** ห้ามเรียก Gemini โดยตรง และการเชื่อม Dify จริงยังปิดอยู่จนกว่าจะกำหนดสัญญา API, citations/revocation, usage/cost และ secret configuration ครบ ตัวเลข Gemini ด้านล่างจึงไม่ใช่ผลของ Dify และไม่ใช่การอนุมัติให้เปิด provider

## อ่านภาพรวมก่อน

โครงการนี้เป็นห้องฝึก SOC จำลอง ผู้เรียนใช้บัญชีเพื่อเรียนบทเรียน ทำรอบฝึก ตรวจ event และ ticket แล้วจึงทำข้อสอบ ระบบแยกข้อมูลฝึกออกจากเฉลยข้อสอบ และให้ backend เป็นผู้ตรวจสิทธิ์กับบันทึกความคืบหน้า หน้าเว็บเป็นส่วนแสดงผล ไม่ใช่ที่เก็บคะแนนหรือสิทธิ์ที่เชื่อถือได้

คำที่พบในเอกสาร:

| คำ | ความหมายง่าย ๆ |
|---|---|
| API | ช่องทางมาตรฐานที่หน้าเว็บใช้ขอข้อมูลหรือสั่งงาน backend |
| Backend | ระบบหลังบ้านที่ตรวจสิทธิ์ ประมวลผล และคุยกับฐานข้อมูล |
| PostgreSQL | ฐานข้อมูลหลักที่บันทึกบัญชี งาน และความคืบหน้า |
| Migration | ขั้นตอนเปลี่ยนโครงสร้างฐานข้อมูลแบบมีลำดับและตรวจย้อนหลังได้ |
| Worker / job | โปรแกรมเบื้องหลังที่ทำงานต่อ แม้ผู้ใช้ปิดหน้าเว็บ เช่น ปล่อย event ตามเวลา |
| Fixture | ข้อมูลเหตุการณ์จำลองที่เตรียมไว้สำหรับการฝึกหรือทดสอบ |
| Ground truth | เฉลยหรือข้อเท็จจริงจริงของโจทย์ ซึ่งต้องเก็บฝั่ง server และจำกัดสิทธิ์ |
| Mock | ตัวแทนจำลองของบริการภายนอก ใช้ทดสอบโดยไม่ส่งข้อมูลหรือเรียกเก็บค่าใช้จ่ายจริง |
| RAG | วิธีค้นเอกสารที่อนุมัติมาเป็นบริบทก่อนให้ AI ตอบ |
| Citation | การอ้างกลับไปยัง event หรือเอกสารที่รองรับคำตอบ |
| Acceptance | การตรวจตามเกณฑ์ที่กำหนดไว้ ว่าพฤติกรรมสำคัญใช้งานได้จริง |
| Local / CI / staging / production | เครื่องนักพัฒนา / ระบบตรวจอัตโนมัติ / ระบบทดสอบก่อนจริง / ระบบที่เปิดใช้จริง |

## ลำดับงานและเหตุผล

งานเรียงจากฐานที่ต้องมีไปสู่ความสามารถที่ซับซ้อน: วางข้อตกลง → ฐานข้อมูลและ CI → บัญชี → ข้อมูลจำลอง → runner และ investigation → AI/evaluation/RAG → บทเรียน/ข้อสอบ → ปฏิบัติการและตรวจช่องว่าง การมีหน้าจอหรือไฟล์โค้ดอย่างเดียวไม่เท่ากับผ่าน acceptance; ต้องดู test ที่รันจริงและสิทธิ์ของข้อมูลด้วย

### ข้อ 01 — วางสัญญาระบบและโครงเริ่มต้น

**ทำอะไร:** กำหนดว่า frontend, API, database, worker และเอกสารสัญญาจะรับผิดชอบอะไร สร้าง scaffold ของ Next.js และ FastAPI พร้อม health checks, lockfiles และโครง OpenAPI/SRS

**ทำไมต้องเริ่มตรงนี้:** ถ้ายังไม่กำหนดว่าใครเป็นเจ้าของ auth, คะแนน, ข้อสอบ และข้อมูลส่วนตัว แต่ละส่วนอาจสร้างกติกาซ้ำหรือเปิดข้อมูลเกินจำเป็น การกำหนดข้อสอบแบบ blind ตั้งแต่ต้นช่วยกันไม่ให้หน้าเว็บรับเฉลยมาแล้วค่อยพยายามซ่อน

**หลักฐานเดิม:** วันที่ 13 ต.ค. 2026 มีผล build/typecheck/lint, OpenAPI validation, backend/frontend smoke และ prototype regression ผ่านตามรายงาน แต่ตอนนั้นมีเพียง foundation/scaffold; DB readiness ตั้งใจตอบ unavailable และยังไม่มี auth, runner, exam, RAG หรือ deployment ครบ

**อ่านต่อ:** [รายงานข้อ 01](step-01-verification.md), [SRS](srs.md), [OpenAPI](openapi.yaml)

### ข้อ 02 — PostgreSQL และการเปิดระบบในเครื่อง

**ทำอะไร:** วาง Compose, PostgreSQL, migrations, role แยกตามหน้าที่, secret files สำหรับ local และ readiness checks ตั้งฐาน auth เริ่มต้น

**ทำไมสำคัญ:** ข้อมูลต้องอยู่ในฐานข้อมูลหลัง refresh/restart และ API/worker ไม่ควรทำงานด้วยสิทธิ์ owner หรือ superuser ถ้าใช้ role ใหญ่เกินไป bug ใน API อาจกลายเป็นการอ่านหรือแก้ข้อมูลทั้งหมด

**หลักฐานเดิม:** รายงาน 13 ต.ค. บันทึก fresh/repeat/concurrent migration, checksum/drift guard, permission tests, provisioning, restart persistence และ Compose integration ผ่านบน PostgreSQL 17.11/Docker Engine ใน environment ที่ระบุ

**ขอบเขต:** ฐานเริ่มต้นมี auth และ operations tables ยังไม่มี scenario, run, job, exam หรือ RAG tables ในเวลานั้น; เพิ่มใน migration ขั้นถัดไป

**อ่านต่อ:** [รายงานข้อ 02](step-02-verification.md), [คู่มือ local](local-development.md), [Database](database.md)

### ข้อ 03 — CI และการตรวจอัตโนมัติ

**ทำอะไร:** ตั้ง workflow ให้ตรวจ prototype, backend, frontend, integration และผลรวมของ jobs พร้อม gate ที่ fail หาก job จำเป็น fail, ถูกยกเลิก หรือหายไป

**ทำไมสำคัญ:** ช่วยจับปัญหาก่อนรวมโค้ด และทำให้ผลตรวจทำซ้ำได้ CI ผ่านไม่เท่ากับเปิด branch protection แล้ว; protection เป็นการตั้งค่าของ GitHub แยกต่างหาก

**หลักฐานเดิม:** รายงานมีทั้งรอบ CI ที่ล้มจริงและรอบแก้แล้วผ่าน พร้อม actionlint, local Compose, integration tests และ artifact upload หลักฐาน branch protection ติดข้อจำกัดแพ็กเกจ/สิทธิ์ในเวลานั้น จึงไม่อ้างว่าเปิดบังคับ merge แล้ว

**อ่านต่อ:** [รายงานข้อ 03](step-03-verification.md), [คู่มือ CI local](ci-local.md), [CI/CD](ci-cd.md)

### ข้อ 04 — บัญชี การเข้าสู่ระบบ และการแบ่งสิทธิ์

**ทำอะไร:** สมัคร/login/logout, opaque session cookie, password hashing, CSRF/Origin checks, rate limiting, account state และตรวจ owner/assignment ใน backend พร้อม Guest demo แบบอ่านอย่างเดียว

**อธิบายง่าย ๆ:** cookie เป็นบัตรผ่านที่ browser ส่งให้ API; server เก็บ hash ของ token ไม่เก็บ token ดิบ ส่วน CSRF/Origin ช่วยยืนยันว่าคำสั่งเปลี่ยนข้อมูลมาจากเว็บที่ตั้งใจ ไม่ใช่เว็บอื่นแอบสั่งผ่าน browser

**หลักฐานเดิม:** PostgreSQL integration ตรวจ session rotation/revoke, concurrent registration, CSRF, owner mismatch และ role scope; Chromium ทดสอบ register → login → refresh → logout ผ่าน proxy และ Guest demo read-only; รายงานอ้าง GitHub CI ผ่านบน SHA ที่ระบุ

**ขอบเขต:** ตอนนั้นยังไม่มี run, lesson, exam, password reset, email verification หรือระบบ admin แบบครบ อย่าใช้ผล auth tests มาอ้างว่าทุก endpoint ของระบบได้รับการตรวจสิทธิ์แล้ว

**อ่านต่อ:** [รายงานข้อ 04](step-04-verification.md), [คู่มือ auth](auth-development.md)

### ข้อ 05 — สถานการณ์จำลองและแยก training จาก exam

**ทำอะไร:** สร้าง scenario catalog แบบมีเวอร์ชัน, event fixtures ฝั่ง server, private ground truth และแยกชุดข้อมูลฝึกออกจากข้อสอบ

**ทำไมสำคัญ:** detector และผู้เรียนควรเห็นเฉพาะ event ที่ปล่อยแล้ว ส่วนเฉลยอยู่ในพื้นที่ privileged การซ่อนเฉลยด้วย CSS หรือไม่แสดงในหน้าเว็บไม่พอ ถ้า API ส่งเฉลยออกมาแล้ว

**หลักฐานเดิม:** seed ซ้ำ/ทำพร้อมกันได้โดยไม่สร้างซ้ำ, API/worker อ่าน truth ไม่ได้, evaluator อ่านได้ตามสิทธิ์, browser catalog/responsive checks และ asset leakage test ผ่านตามรายงาน

**ขอบเขต:** S02 เปิดเป็น training ในช่วงรายงาน ส่วน S01/S03/S04/S05 ยังทยอยเปิดตาม acceptance ของ runner/detection; ข้อ 05 เพียงอย่างเดียวไม่ได้แปลว่ารอบฝึกและข้อสอบครบ

**อ่านต่อ:** [รายงานข้อ 05](step-05-verification.md), [คู่มือ scenario](scenario-development.md)

### ข้อ 06 — งานเบื้องหลังและ runner ที่ทำต่อได้

**ทำอะไร:** เพิ่ม runs, events, jobs, idempotency, worker lease และการกู้คืนเมื่องานค้างหรือ worker restart

**อธิบายง่าย ๆ:** browser ไม่ใช่นาฬิกาของ simulation ถ้าปิด browser แล้วเหตุการณ์ควรยังเดินตาม schedule ฝั่ง server ส่วน lease คือสิทธิ์ทำ job ชั่วคราว; fencing token กัน worker เก่าที่ lease หมดแล้วกลับมาเขียนผลทับ worker ใหม่

**หลักฐานเดิม:** integration ตรวจ race ระหว่าง pause/release, crash/recovery, expired lease และ stale worker; continuity test เริ่ม S02, logout/ปิด browser, restart worker แล้วได้ 15 events และ 37 job keys ที่ไม่ซ้ำใน environment ทดสอบ

**ขอบเขต:** ผลนี้ไม่ยืนยันว่า evaluator, คะแนน หรือข้อสอบพร้อม; finish และ evaluation snapshot ถูกทำในขั้นถัดไป

**อ่านต่อ:** [รายงานข้อ 06–10](step-06-10-verification.md), [runner continuity](../frontend/tests/runner-continuity.cjs)

### ข้อ 07 — หน้ารอบฝึกและ Event explorer

**ทำอะไร:** หน้า list/start run, filters, event timeline, request/response/log, pause/resume, cursor pagination และ polling พร้อม backoff

**ทำไมใช้ cursor และ backoff:** cursor ช่วยอ่านเหตุการณ์ต่อจากจุดเดิมโดยไม่ซ้ำหรือข้ามหน้า; backoff ลดการยิง API ถี่เมื่อระบบขัดข้อง และ polling หยุด/ปรับเมื่อ tab ซ่อนหรือ session หมดอายุ

**หลักฐานเดิม:** Chromium flow login → start S02 → อ่าน event → pause → refresh → resume; ตรวจ filter/URL state, pagination, stale response, escaped text, error/recovery และ viewport 375/768/1440 ตามรายงาน

**ขอบเขต:** ใช้ API ที่มีอยู่ ไม่มี migration/domain route ใหม่ในข้อ 07 และผล local ไม่ใช่ผล GitHub ของ changeset ล่าสุดโดยอัตโนมัติ

**อ่านต่อ:** [รายงานข้อ 07](step-07-verification.md)

### ข้อ 08 — Detection, anomaly และ correlation

**ทำอะไร:** rule detection, baseline anomaly, correlation, detection revisions, alerts และ automatic tickets จาก released events

**ตัวอย่างแนวคิด:** rule จับรูปแบบชัด เช่น failed login หลายครั้ง; anomaly เปรียบเทียบจำนวนการอ่านกับ baseline; correlation เชื่อม account/session/asset/time ใน scenario เดียวกัน

**หลักฐานเดิม:** S01–S05 และ normal traffic มี test; S05 สร้าง anomaly; duplicate jobs ไม่ทำให้ alert/ticket ซ้ำ; composite foreign keys กัน evidence ข้าม run; blocked request ไม่ถูกตีความว่า compromise สำเร็จ

**ขอบเขต:** ตัวเลข threshold เป็น configuration ของเวอร์ชัน ไม่ใช่ข้อสรุปว่าตรวจภัยทุกชนิดได้ และการตรวจ local ไม่ใช่ benchmark production

**อ่านต่อ:** ส่วนข้อ 08 ใน [รายงานข้อ 06–10](step-06-10-verification.md)

### ข้อ 09 — Ticket, note และ assessment ที่มีประวัติ

**ทำอะไร:** สร้าง/แก้ ticket, note, evidence references, disposition และ audit/version history พร้อม optimistic concurrency

**อธิบายง่าย ๆ:** `expected_version` คือเลขรุ่นที่ client เห็นตอนเริ่มแก้ ถ้ามีคนอื่นบันทึกก่อน API ส่ง `409 Conflict` และเก็บ draft ไว้ แทนการเขียนทับงานล่าสุดโดยเงียบ ๆ

**หลักฐานเดิม:** ทดสอบ owner/Instructor assignment, cross-run refs, soft delete, version conflict, timeline, filters/cursor และ browser edit history ผ่านตามรายงาน

**ข้อตกลง:** disposition คง `true_positive`, `false_positive`, `undetermined`; ไม่เพิ่มค่าอื่นเองเพราะมีผลต่อ scoring

**อ่านต่อ:** ส่วนข้อ 09 ใน [รายงานข้อ 06–10](step-06-10-verification.md)

### ข้อ 10 — AI analysis adapter และการควบคุม usage (ประวัติ)

**ทำอะไรในช่วงรายงานเดิม:** มี mock เป็นค่าเริ่มต้นและเคยทดสอบ Gemini Free Tier แบบ opt-in กับข้อมูลจำลอง ตรวจ structured output, citations, quota reservation และสถานะ usage ที่ไม่ทราบ

**ความหมายของ `unknown`:** หาก timeout หลังส่งคำขอ ไม่รู้ว่าผู้ให้บริการประมวลผลหรือคิด usage ไปแล้วหรือไม่ จึงต้องคง reservation ไว้และห้ามเดาเป็นศูนย์/ retry อัตโนมัติจนกว่าจะ reconcile

**หลักฐานเดิม:** รายงานมี local provider tests และ synthetic S02 call ตาม config/งบที่อนุมัติในเวลานั้น พร้อม usage ที่บันทึก แต่การเรียกนั้นเป็นอดีต ไม่ใช่การเชื่อม provider ปัจจุบัน

**สถานะปัจจุบัน:** Dify เป็น provider เป้าหมายเดียว; Gemini adapter/config เก่าเป็น legacy และไม่ควรถูกเรียกโดย flow ใหม่ Dify runtime ยังคงปิดจนมี endpoint/key, app/workflow contract, citation/revocation, usage/cost controls และ tests ที่อนุมัติครบ

**อ่านต่อ:** ส่วนข้อ 10 ใน [รายงานข้อ 06–10](step-06-10-verification.md), [รายงานข้อ 12](step-12-verification.md), [SRS](srs.md)

### ข้อ 11 — Evaluation, finish และ Instructor

**ทำอะไร:** freeze cutoff เมื่อจบ training run, สร้าง immutable evaluation snapshot และแยก evaluator credential จาก API/worker พร้อม instructor assignment/comment/export

**ทำไมต้อง freeze:** ถ้า event หรือผลวิเคราะห์มาช้าหลังจบรอบ ไม่ควรเปลี่ยนคะแนนย้อนหลังโดยไม่ตั้งใจ snapshot เป็นภาพข้อมูล ณ จุดจบที่ตรวจซ้ำได้

**หลักฐานเดิม:** PostgreSQL tests ครอบ cutoff, late analysis fencing, snapshot immutability, role grants และ assignment; browser ทดสอบ finish → evaluation → JSON export บนข้อมูลจำลอง

**สิ่งที่ยังต้องระวัง:** รายงานระบุ human score `unavailable` จนกว่าจะมี rubric/policy; C ยัง unavailable ในช่วงนั้น และ GitHub CI ของ changeset บางชุดยังรอยืนยันในรายงาน

**อ่านต่อ:** [รายงานข้อ 11](step-11-verification.md)

### ข้อ 12 — Provider budget และ unknown-usage controls (หลักฐานเก่า)

**ทำอะไรในรายงานเดิม:** บันทึก global/per-user caps, reservation ก่อน dispatch, แยก logical request กับ component calls, cooldown 429, ไม่ retry ambiguous calls และมี operator reconciliation

**ทำไมจองก่อนเรียก:** ป้องกัน worker หลายตัวส่งคำขอพร้อมกันจนเกินโควตา; เมื่อรู้ usage จริงจึง settle ส่วนต่าง ส่วนที่ยังไม่รู้ต้อง hold ไว้

**หลักฐานเดิม:** มี PostgreSQL concurrency tests และ bounded synthetic provider call ใน Free Tier ซึ่งผูกกับ Gemini policy ณ วันที่ 15 ต.ค. 2026; ไม่ใช่ Dify test และไม่ยืนยัน usage/cost ปัจจุบัน

**สถานะปัจจุบัน:** นโยบาย/implementation เดิมต้องทบทวนให้เข้ากับ Dify usage report และ contract ก่อนเปิด real provider การที่มี reconciliation CLI ไม่ได้แปลว่ามีรายงาน provider สำหรับ calls เก่าครบแล้ว

**อ่านต่อ:** [รายงานข้อ 12](step-12-verification.md), [งานค้างข้อ 11–13](steps-11-13-follow-up.md)

### ข้อ 13 — Knowledge storage และ ingestion (ออกแบบเดิม)

**ทำอะไรในรายงานเดิม:** สร้าง approved corpus manifest, versioned ingestion, fake embeddings, release publish/revoke และ pin knowledge release ต่อ run

**อธิบายง่าย ๆ:** ingestion คือการนำคู่มือที่อนุมัติมาแบ่งเป็นชิ้นและทำดัชนี เพื่อค้นภายหลัง การ publish สร้าง release ที่ตรึงแล้ว; revoke ทำให้แหล่งนั้นหยุดปรากฏแม้ run เก่าเคย pin ไว้

**หลักฐานเดิม:** local PostgreSQL/Compose tests ตรวจ manifest/path, ACL, deduplication, publish/revoke, stale worker และ fake retrieval ได้ แต่ fake embeddings เป็นการทดสอบโครงสร้าง ไม่ใช่หลักฐานคุณภาพความเข้าใจภาษา

**สถานะปัจจุบัน:** pipeline ภายในที่ใช้ pgvector/LangChain เป็นประวัติ/legacy ไม่ใช่สถาปัตยกรรม Dify ที่ผู้ใช้เลือก ทิศทางปัจจุบันคือส่งคำขอไปบริการ RAG ภายนอกผ่าน Dify API เท่านั้น; ห้ามกล่าวว่า Dify เชื่อมแล้วจากผลข้อ 13 เดิม

**อ่านต่อ:** [รายงานข้อ 13](step-13-verification.md), [SRS](srs.md), [รายงาน alignment](implementation-alignment-review.md)

### ข้อ 14 — ตรวจคุณภาพ RAG, citations และ usage

**ทำอะไร:** วัดสองเรื่องแยกกัน: (1) retrieval ดึงเอกสารที่เกี่ยวข้องไหม และ (2) คำตอบอ้างหลักฐานได้ครบไหม พร้อมตรวจ no-match, citation/revocation และ provider usage

**ทำไมแยกสองเรื่อง:** ค้นเอกสารถูกไม่ได้แปลว่าคำตอบถูก; citation ID ที่มีจริงก็ไม่ได้แปลว่าเนื้อหานั้นรองรับ claim การตรวจต้องดูทั้ง relevance ของแหล่งและความหมายของแต่ละข้อความ

**หลักฐานเดิม:** retrieval v2 ได้ developer labels ไทย Recall@5 0.95 / อังกฤษ 1.00 แต่ยังมี Thai miss; self-review ของผู้เขียน implementation ให้ 53/57 claims รองรับครบ (RAG 35/36) ซึ่ง **ไม่ใช่ independent human review** และ baseline answer benchmark มี invalid/provider failures ที่ต้องคงไว้ รายงานยังระบุ unknown usage 6 calls ที่ไม่มี provider report จับคู่ได้

**ยังไม่ผ่านรับรอง:** ต้องมีผู้ตรวจอิสระยืนยัน relevance/grounding, paired answer benchmark บน release/config ที่ถูกต้อง และรายงาน usage ที่เชื่อมกับ 6 calls ได้ หากหา usage report ไม่ได้ให้คงสถานะ unknown ห้ามแก้เป็นศูนย์เอง

**สถานะปัจจุบัน:** ผลชุดนี้มาจาก pipeline/provider รุ่นก่อน Dify จึงไม่ใช่ Dify acceptance; ก่อนเปิด Dify ต้องกำหนด benchmark/citations/usage ตาม integration ใหม่

**อ่านต่อ:** [รายงานข้อ 14](step-14-verification.md), [คู่มือผู้ตรวจ](step-14-review-guide.md), [agent self-review](step-14-agent-review.md)

### ข้อ 15 — บทเรียนและความคืบหน้าฝั่ง server

**ทำอะไร:** บทเรียน versioned มีขั้นเรียงลำดับ; API เก็บ progress ของเจ้าของบัญชีและตรวจ gate ก่อนให้เริ่มข้อสอบ

**ข้อตกลงที่ผู้ใช้ยืนยัน:** ต้อง login ก่อนอ่านเนื้อหาบทเรียน Guest เห็น metadata/ข้อความให้เข้าสู่ระบบเท่านั้น ความคืบหน้าหลัง refresh อ่านกลับจาก server ไม่ใช่ localStorage

**หลักฐานเดิม:** migration/seed, owner-scoped progress, stale version conflict และ exam gate tests; browser ทำบทเรียนครบ refresh แล้ว progress อยู่ ตรวจ viewport 375/768/1440 และเริ่ม exam หลังเรียนจบได้

**ข้อจำกัด:** รายงานมี local Compose/browser evidence แต่ไม่อ้าง GitHub CI หรือ full accessibility audit สำหรับทุก changeset

**อ่านต่อ:** [รายงานข้อ 15](step-15-verification.md), [Learning path](learning-path.md)

### ข้อ 16 — Blind exam และการส่งคำตอบแบบ immutable

**ทำอะไร:** server เลือก case, เปิดข้อมูลข้อสอบแบบไม่เปิดเฉลย, ตรวจ lesson gate และบันทึก submission/cutoff แบบ atomic

**คำศัพท์:** blind projection หมายถึง API ส่งเฉพาะข้อมูลที่ผู้เรียนควรเห็น ไม่ส่ง private truth, initial severity หรือ AI hints; atomic submit หมายถึงการตรึงคำตอบและ cutoff พร้อมกันเพื่อกันการแก้หลังส่ง

**Retake policy ในรายงานล่าสุด:** สูงสุด 3 attempts ต่อ case ใน rolling 24 ชั่วโมง (สูงสุด 9 ต่อ level), cooldown 1 ชั่วโมงหลัง fail และ attempt หมดอายุ 24 ชั่วโมง; การเริ่ม attempt พร้อมกันถูก serialize เพื่อไม่ให้มี active attempt ซ้ำ

**หลักฐานเดิม:** PostgreSQL tests ตรวจ idempotency, blind DTO, submit/replay, owner scope, lesson gate, concurrent review/unlock, case cap และ retake race หลัง cooldown หมด; browser ตรวจ submit → `needs_review`, feedback, cooldown rejection. Browser journey ที่รอ cooldown หมดแล้วเริ่ม retake จริงยังเป็นช่องว่างตามรายงานล่าสุด

**สถานะ:** รายงานวันที่ 21 ต.ค. ยังระบุ Step 16 ไม่ผ่านตรวจรับทั้งหมด และ GitHub CI ของ changes ล่าสุดยังรอยืนยัน แม้ local tests ผ่าน

**อ่านต่อ:** [รายงานข้อ 16](step-16-verification.md)

### ข้อ 17 — Grading, Instructor review และ unlock

**ทำอะไร:** ให้คะแนนด้วย rubric แบบ deterministic, เก็บ revision, แสดง feedback ตามสิทธิ์ และปลดล็อก level เมื่อครบเกณฑ์ โดย Instructor review มี audit

**นโยบายที่บันทึก:** rubric `soc-foundations-v1` มี 4 criteria คะแนน 0–2 รวมผ่านอย่างน้อย 6/8 และ criteria สำคัญต้องได้อย่างน้อย 1; ข้อกำหนดรายงานยังบอกให้ใช้ evidence จาก released events ใน run เดียวกัน กรณีกำกวมหรือข้อมูลไม่ครบต้องไม่ auto-pass

**หลักฐานเดิม:** PostgreSQL integration ครอบ assignment-scoped review, concurrent review, unlock, append-only override/audit; browser journey ให้ Instructor ตรวจ submission จริงใน disposable DB แล้ว learner refresh เห็น feedback

**ข้อจำกัด:** AI grading/provider grading ไม่เปิด การผ่าน local test ไม่เท่ากับอนุมัติ AI grading; รายงานระบุ acceptance ของ Step 17 ยังขึ้นกับ Step 14 และยังมี interleavings ที่ไม่ได้ครอบคลุมทั้งหมด

**อ่านต่อ:** [รายงานข้อ 17](step-17-verification.md), [SRS decision register](srs.md)

### ข้อ 18 — Staging, release และ operations

**ทำอะไร:** วางการ build image, deploy API/worker/web, migration แบบ one-shot, health checks, rollback และ backup/restore

**สิ่งที่ทดสอบได้ในรายงาน:** Dockerfiles, pinned images, local Compose, disposable integration, health/worker/evaluator checks และ local browser flows

**สิ่งที่ยังไม่มีหลักฐาน:** staging host/registry/domain, immutable release image digests, deployment run, HTTPS acceptance, rollback drill และ restore จาก backup ไปฐานใหม่ ดังนั้น local Docker ที่เปิดได้ไม่แปลว่าระบบ production พร้อม

**อ่านต่อ:** [รายงานข้อ 18](step-18-verification.md), [CI/CD](ci-cd.md)

### ข้อ 19 — ตรวจความครอบคลุมและช่องว่างก่อนส่งมอบ

**ทำอะไร:** เทียบ requirements กับ implementation และ test evidence รวม flow ตั้งแต่สมัครจนถึง feedback หลังสอบ เพื่อหาขั้นที่ยังขาด

**หลักฐานล่าสุดในรายงาน:** วันที่ 21 ต.ค. 2026 local disposable Compose ผ่าน integration 81, HTTP smoke 3 และ browser E2E 26 passed / 1 skipped พร้อม worker/evaluator readiness; ตรวจ retake race ใน PostgreSQL และ cooldown rejection ใน browser

**ยังไม่ปิด:** GitHub CI สำหรับ changes ล่าสุด, browser journey ที่รอ cooldown หมดแล้วเริ่ม retake, export coverage, accessibility/load audit และ staging/production deployment/rollback/restore ยังไม่มีหลักฐานตามรายงาน ผล local ไม่แทนรายการเหล่านี้

**อ่านต่อ:** [รายงานข้อ 19](step-19-verification.md), [implementation alignment review](implementation-alignment-review.md)

## เจาะลึกว่าแต่ละขั้นต่อกันอย่างไร

ส่วนนี้ขยายจากภาพรวมข้างบน โดยเล่าลำดับข้อมูลและการตัดสินใจที่เกิดขึ้นจริงในระบบ เป้าหมายคือให้คนอ่านเห็นว่าแต่ละ test ป้องกันความผิดพลาดแบบใด ไม่ใช่เพียงจำชื่อไฟล์หรือจำนวน test

### ข้อ 01 — จากข้อกำหนดไปสู่สัญญาที่ตรวจได้

ก่อนมีโค้ดหลายส่วน ทีมต้องตกลงก่อนว่า request/response รูปแบบใดถือเป็นสัญญา และส่วนใดยังเป็นร่าง OpenAPI ช่วยให้ frontend, backend และ test อ้างชื่อ field/status code ชุดเดียวกัน; SRS เก็บเหตุผลกับประเด็นที่ยังต้องตัดสินใจ ส่วน requirement mapping ช่วยไล่ย้อนจากข้อกำหนดไปยัง endpoint/test ได้

ผลตรวจข้อ 01 จึงต้องอ่านเป็น “โครงฐานที่ build ได้” ไม่ใช่ผลิตภัณฑ์ SOC ที่ทำงานครบ ตัวอย่างเช่น health endpoint บอกได้ว่า process ตอบสนอง แต่ถ้า database readiness ยัง unavailable ก็ยังใช้ยืนยันว่าระบบเก็บข้อมูลได้ไม่ได้ การแยก draft operation ออกจาก approved operation สำคัญ เพราะการมี schema ตัวอย่างไม่ได้ทำให้ route นั้นเปิดใช้งานจริง

### ข้อ 02 — จากฐานเปล่าสู่ข้อมูลที่รอดหลัง restart

การทดสอบ migration เริ่มจากฐานว่างเพื่อยืนยันว่าตารางและ grants สร้างขึ้นได้ จากนั้นรันทับอีกครั้งเพื่อเช็ก idempotency และจำลอง migration พร้อมกันเพื่อเช็ก advisory lock การตรวจ checksum ทำให้การแก้ revision ที่เคยใช้แล้วถูกตรวจพบ แทนที่จะทำให้ฐานของแต่ละเครื่องค่อย ๆ ต่างกันโดยไม่รู้ตัว

Compose แยก API, worker, bootstrap, migration และฐานทดสอบ บัญชีของแต่ละ process มีสิทธิ์เท่าที่ต้องใช้เท่านั้น การทดสอบหยุดแล้วเปิด database ใหม่โดยคง named volume จึงตรวจได้ว่าข้อมูลรอดจริง โดยไม่ลบ volume ของระบบหลักเพื่อให้ test สะอาด

### ข้อ 03 — CI ตรวจทั้งงานย่อยและผลรวม

workflow มี jobs แยกตามส่วนเพื่อบอกได้ว่าความผิดพลาดอยู่ frontend, backend, prototype หรือ integration ส่วน ci-gate อ่านผลที่เครื่องมือส่งออกและตัดสินแบบ fail-closed: ถ้า job หาย, ถูก cancel หรือสถานะอ่านไม่ได้ ผลรวมต้องไม่เป็น success การแนบ test reports เป็น artifact ทำให้ตรวจรายละเอียดหลัง job จบได้

มีรอบแรกที่ CI ล้มจาก import-smoke bug และรอบถัดมาที่แก้แล้วผ่าน รายงานจงใจเก็บทั้งสองรอบไว้เพื่ออธิบายว่า failure ถูกจับได้อย่างไร การผ่าน workflow ไม่ได้สร้าง branch protection โดยอัตโนมัติ; GitHub plan/setting เป็นชั้นควบคุมอีกชั้นหนึ่ง

### ข้อ 04 — การยืนยันตัวตนไม่เท่ากับการอนุญาตทุกข้อมูล

การ login พิสูจน์เพียงว่า session ใช้ได้ แต่ทุก resource ยังต้องตรวจเจ้าของและ assignment อีกครั้ง API ใช้ cookie แบบ opaque; browser ไม่ได้รับ role หรือ user ID ที่ใช้ตัดสินสิทธิ์จาก client ผู้สมัครใหม่เป็น Analyst เท่านั้นและไม่ auto-login ส่วน Instructor ถูก provision ด้วย operator process ตามขอบเขตที่รายงาน

การทดสอบ owner mismatch และ Instructor นอก assignment ที่ตอบ 404 ช่วยไม่เปิดเผยว่าข้อมูลของคนอื่นมีอยู่หรือไม่; 403 ใน admin policy ใช้กับความสามารถที่ผู้ใช้ไม่มีสิทธิ์ตาม contract การทดสอบ CSRF/Origin ตรวจ mutation โดยเฉพาะ เพราะการอ่าน session แล้วไม่เพียงพอที่จะกันเว็บภายนอกสั่งเปลี่ยนข้อมูล

### ข้อ 05 — Fixture มีหลายชั้นและใช้แทนกันไม่ได้

ข้อมูลอย่างน้อยแยกเป็น catalog metadata, released training events, exam bank และ private ground truth Catalog บอกได้ว่ามีสถานการณ์อะไร แต่ไม่ควรมี event อนาคตหรือเฉลย การ seed ต้องทำซ้ำได้โดยไม่สร้างเวอร์ชันซ้ำ และการเปลี่ยน fixture ที่เผยแพร่แล้วควรออก revision แทนการแก้เนื้อหาใต้ run เดิม

ข้อทดสอบ grants สำคัญกว่าการตรวจ UI อย่างเดียว: ถ้า API/worker query ตารางเฉลยไม่ได้ ต่อให้มี route bug ก็ยังมีชั้นฐานข้อมูลช่วยป้องกัน ส่วน browser asset test ตรวจว่า fixture/private truth ไม่ถูกใส่ใน JavaScript bundle โดยไม่ได้ตั้งใจ

### ข้อ 06 — Job queue ทำให้ simulation ไม่ผูกกับ browser

API สร้าง run และ job ใน transaction ที่กำหนด จากนั้น worker claim job ด้วย lease ที่หมดอายุได้ ถ้า worker หยุดทำงาน job กลับมาทำต่อได้ แต่ stale worker ต้องพิสูจน์ lease token ก่อน commit การตรวจ run-lock ก่อน job/resource ทำให้ pause/finish และ event release มีลำดับที่คาดเดาได้

หลักฐาน continuity ที่มีความหมายคือเริ่ม run ผ่านเว็บ แล้ว logout/ปิด browser/หยุด worker ก่อนเปิด worker ใหม่และตรวจฐานข้อมูล พบ event กับ dedupe keys ไม่ซ้ำ นี่ตรวจพฤติกรรมข้าม process จริงกว่าการเรียกฟังก์ชัน worker ตรง ๆ ใน unit test แต่ยังเป็น scenario S02 ในเครื่อง ไม่ใช่การรับรองทุก scenario หรือ hosting

### ข้อ 07 — หน้าตรวจเหตุการณ์รักษาบริบทของผู้ใช้

หน้ารอบฝึกเก็บ filter และ event ที่เลือกไว้ใน URL เพื่อ refresh หรือส่งลิงก์ภายใน session แล้วกลับมาจุดเดิมได้ โดยข้อมูลจริงยังอ่านจาก API ทุกครั้ง Cursor ใช้โหลดต่อจากหน้าเดิม; `after_seq` ใช้ดึง event ใหม่ตามลำดับ ห้ามส่งสองรูปแบบพร้อมกันตาม contract

ข้อมูล request/response/log เป็นข้อความที่ไม่น่าเชื่อถือ จึง escape เมื่อแสดงผล ไม่แปลงเป็น HTML ที่รันได้ การทดสอบ stale response ตรวจว่าผลตอบกลับจาก filter/session เก่าไม่ทับหน้าปัจจุบัน และ 401/403/404/422 หยุด retry เพราะ retry ซ้ำไม่ทำให้สิทธิ์หรือข้อมูลถูกต้องขึ้น

### ข้อ 08 — Detection อาศัยหลักฐานที่ปล่อยแล้ว

Detector อ่าน released events และ versioned config ของ run เท่านั้น ไม่อ่าน scenario label หรือ ground truth; ถ้ารู้เฉลย detector ก็จะดูเหมือนแม่นแต่ไม่ใช่การตรวจจากสัญญาณที่ผู้เรียนมีจริง การ deduplicate detection/ticket ป้องกัน job ที่ถูกส่งซ้ำจากสร้าง incident ซ้ำ ส่วน revision ใหม่บันทึกหลักฐานที่เพิ่มภายหลังโดยรักษาประวัติ

ข้อทดสอบ S05 ตรวจว่า anomaly เกิดจากข้อมูล event ตามเกณฑ์ ไม่ใช่เพราะ code อ่านชื่อ scenario แล้วสร้างผลตามเฉลย การทดสอบ normal traffic และ blocked request ช่วยตรวจ false positive และการใช้ถ้อยคำ: 403 ยืนยันว่าคำขอถูกปฏิเสธ ไม่ได้พิสูจน์ว่าระบบถูกเจาะหรือไม่ถูกเจาะจากเหตุการณ์อื่น

### ข้อ 09 — การสืบสวนต้องแก้ไขย้อนหลังแบบตรวจสอบได้

Ticket เป็นข้อสรุปของนักวิเคราะห์ ไม่ใช่ raw event; note และ assessment จึงมี version/history แยกจากหลักฐานดิบ Evidence ref ต้องอยู่ใน run เดียวกันเพื่อกัน ticket หนึ่งไปอ้าง event จากอีกรอบ การ soft-delete ซ่อนรายการจากผู้ใช้แต่ยังต้องรักษาความสัมพันธ์/denominator ตาม policy

เมื่อผู้ใช้สองคนเปิด ticket รุ่นเดียวกัน คนแรกบันทึกแล้วเพิ่ม version; คนที่สองจึงได้ 409 แทนการเขียนทับ ระบบเก็บ draft ให้แก้ต่อได้ การทดสอบกรณีนี้ตรวจทั้ง API conflict และประสบการณ์ UI หลัง refresh ไม่ใช่ตรวจแค่ status code

### ข้อ 10 — AI เป็นผู้ช่วยวิเคราะห์ ไม่ใช่เจ้าของการตัดสินใจ

adapter รับ evidence snapshot ที่ผ่านการ redact และส่งออก structured result ที่ตรวจด้วย schema ก่อนเก็บ citations ต้องเป็น subset ของแหล่งที่ request นั้นได้รับ หากโมเดลตอบข้อความไม่ตรง schema หรืออ้าง ID ที่ไม่ได้ให้มา ผลต้องเป็น invalid/unavailable ไม่ fallback ไปแสดง raw provider text

Rule/anomaly เปิด ticket ได้โดยไม่รอ AI; provider timeout จึงไม่ควรหยุดการสืบสวน การเรียก provider อยู่นอก database transaction เพื่อไม่ล็อกแถวขณะรอ network และระบบแยก mock/real/status ให้ UI บอกสถานะตามจริง ส่วนการทดลอง Gemini ในรายงานเดิมเป็นข้อมูลย้อนหลังตามที่ระบุข้างต้น ไม่ใช่ implementation ที่ควรเปิดใช้ต่อ

### ข้อ 11 — Finish สร้างจุดตัดที่ไม่เลื่อนตามงานช้า

เมื่อผู้ใช้ finish ระบบล็อก run, บันทึก cutoff และสร้างงาน evaluator ใน transaction เดียว งานที่ปล่อย/ประมวลผลหลัง cutoff ถูก fence ไม่ให้เปลี่ยน snapshot เดิม evaluator ใช้สิทธิ์แยกจาก API/worker เพื่อเข้าถึงข้อมูลที่จำเป็นต่อการวัดผลเท่านั้น

Training truth มี policy เฉพาะ: เจ้าของอ่านได้หลัง completion; Instructor อ่านได้เฉพาะ run ที่ assign และมี audit ตามรายงาน ส่วน exam truth มี blind policy แยก ไม่ควรอนุมานจาก training endpoint ว่าข้อสอบเปิดเฉลยได้ การวัด detector metrics, human score และ AI quality แยกกันเพื่อไม่ให้คะแนนประเภทหนึ่งปลอมเป็นอีกประเภท

### ข้อ 12 — การคุม budget ต้องคิดถึงคำขอที่ไม่ทราบผล

ระบบนับ logical request แยกจาก provider dispatch/component calls เพราะคำถามหนึ่งอาจต้อง embedding, token count และ generation หลายครั้ง การ reserve ก่อนส่งช่วยทำ admission แบบ atomic ระหว่าง worker หลายตัว; เมื่อ provider รายงาน usage จึง settle และคืนเฉพาะส่วนที่ยืนยันว่าไม่ได้ใช้

กรณี timeout ต่างจาก HTTP 429: timeout อาจเกิดหลัง provider รับคำขอ จึงเป็น unknown และต้อง hold; 429 เป็นคำปฏิเสธที่รู้แน่ตาม response และอาจกำหนด cooldown ได้ การ reconcile ต้องอ้าง provider report ที่ตรวจย้อนกลับได้ ไม่ใช่ใส่เลขเพื่อปลด hold เฉย ๆ ข้อจำกัดจริงของรายงานเดิมคือ 6 calls ยังจับคู่ usage ไม่ได้

### ข้อ 13 — Ingestion ที่ปลอดภัยต้องควบคุมแหล่งข้อมูล

รายงาน pipeline ภายในใช้ manifest ระบุไฟล์ที่อนุมัติ, revision/hash และ canonical path; ปฏิเสธ URL อิสระหรือไฟล์ที่อยู่นอก approved directory การแบ่ง chunk เก็บ locator/hash เพื่อย้อนกลับไปยังต้นฉบับและตรวจการเปลี่ยนแปลงได้

โปรไฟล์ fake embedding 16 มิติใช้ตรวจ schema, dimension, ingestion, ACL และ retrieval ordering แบบทำซ้ำได้เท่านั้น ไม่ได้วัด semantic quality จริง เมื่อ revoke ต้องไม่ถูกคืนผลผ่าน release เก่าหรือ projection อื่น ทั้งหมดนี้เป็นเนื้อหาของระบบเดิม ไม่ใช่สิ่งที่จะส่งเข้า Dify โดยอัตโนมัติ; corpus ที่ Dify ใช้ต้องมี approval และขอบเขตใหม่ชัดเจน

### ข้อ 14 — แยกคุณภาพ retrieval, grounding และภาษา

Recall@5 ตอบว่าในผลค้น 5 อันดับแรกมีแหล่งที่ผู้ตรวจเห็นว่าเกี่ยวข้องหรือไม่; MRR ดูตำแหน่งของผลที่เกี่ยวข้อง ส่วน supported-claim rate ตรวจว่าข้อความแต่ละ claim มีหลักฐานรองรับครบหรือไม่ ต้องรายงานแยกภาษาและ RAG/no-RAG เพราะค่าเฉลี่ยรวมอาจซ่อนปัญหาในภาษาใดภาษาหนึ่ง

รายงาน agent self-review พบ claim ที่มี citation แต่มีส่วนเกินหลักฐาน เช่น event แสดง 403 แต่คำตอบเติมข้อสรุปเกี่ยวกับ URL หรือ authentication ที่ไม่มีใน event/context การนับ claim ว่ารองรับต้องดูทั้งประโยค ไม่ใช่เพียงว่ามี citation ID จริง การสุ่มตัวอย่างและ label โดยผู้เขียนเองยังมี bias จึงต้องให้ผู้ตรวจอิสระยืนยันก่อนใช้เป็น acceptance

ผล retrieval v2 ไทย 0.95/อังกฤษ 1.00 มาจาก developer labels และ corpus เล็กเพียงสอง chunks; ไม่ควรตีความว่า RAG ตอบถูก 95–100% โดยทั่วไป หรือว่า paired answer quality ดีกว่า baseline อีกทั้ง historical unknown usage 6 calls ยังเป็นคนละประเด็นกับ quality review และต้อง reconcile แยกกัน

### ข้อ 15 — บทเรียนสร้าง gate ที่ server เป็นเจ้าของ

บทเรียนมี version และลำดับขั้นตอน: อ่าน Method/Path, Response, account/IP, timeline และข้อจำกัดของหลักฐาน ผู้เรียนส่ง completion ทีละ step ด้วย `expected_version`; server ตรวจลำดับและเจ้าของบัญชี การจบ lesson เป็นเพียงเงื่อนไขหนึ่ง ไม่ใช่ผลสอบผ่าน

เมื่อ browser refresh UI ขอ progress จาก API ใหม่ จึงตรวจได้ว่าความคืบหน้า persist จริงและบัญชีอื่นอ่านไม่ได้ การทดสอบ exam start ก่อน lesson complete ต้องถูกปฏิเสธจาก backend แม้ client จะพยายามเรียก endpoint โดยตรง Guest เห็น metadata กับ login prompt ตามการตัดสินใจของผู้ใช้ แต่ไม่เห็น lesson body

### ข้อ 16 — ข้อสอบต้องไม่เปิดคำใบ้ก่อนส่ง

ตอนเริ่ม attempt server ตรวจ session, lesson/level gate, quota, active attempt, cooldown และ idempotency ก่อนเลือก case จาก bank การเลือกฝั่ง server ป้องกัน client ขอ case ที่ต้องการหรือแก้ run mode เอง API สร้าง projection ที่ allowlist เฉพาะคำถาม/evidence ที่ผู้เรียนควรเห็น

ตอน submit ระบบ freeze answer, evidence/run cutoff และ submission state ด้วย transaction เดียว จึงไม่มีช่องให้แก้คำตอบหลังเห็นผลหรือเรียก finish แบบ training เพื่อข้าม grading การ replay key เดิมต้องคืนผลเดิม; key เดิมกับ body ต่างต้อง conflict ตาม contract

Retake tests ที่มีตรวจ quota/case cap/cooldown และ concurrency บน PostgreSQL แต่รายงานยังระบุช่องว่าง browser journey หลัง cooldown หมด นี่เป็นตัวอย่างว่าการทดสอบ API race ผ่านยังไม่เท่ากับ UX ครบตั้งแต่ต้นจนจบ

### ข้อ 17 — คะแนนต้องมาจากกติกาที่อ่านตรวจได้

Rubric แบบ deterministic ทำให้คะแนนจากคำตอบเดียวกันมีเหตุผลเทียบกันได้ ระบบเก็บ grading revisions เพื่อไม่เขียนทับคะแนนเดิม; Instructor review ตรวจเฉพาะผู้เรียนที่ถูก assign และการเปิด truth มี audit Learner DTO แสดง feedback ตามที่อนุมัติ ไม่ส่ง full answer key

`needs_review` เป็นสถานะปลอดภัยเมื่อข้อมูลกำกวม/ระบบประเมินไม่พร้อม; provider ล่มไม่ควรแปลว่าผ่านหรือไม่ผ่านเอง Unlock สร้างได้ครั้งเดียวเมื่อผ่านเงื่อนไขและเก็บ audit; override เพิ่ม revision แต่ไม่ย้อนถอน unlock ที่ได้ไปแล้วตาม policy ในรายงาน

รายงานวันที่ 20 ต.ค. บันทึก full browser journey Analyst submit → Instructor review → Analyst refresh แล้วเห็น feedback บน PostgreSQL จริงในฐานทดสอบ แต่การตรวจรับข้อ 17 ยังขึ้นกับข้อ 14 และยังไม่มี acceptance AI grading ซึ่งไม่ได้เปิดใช้

### ข้อ 18 — Local Compose ไม่ใช่ staging

Local Compose ตรวจว่าภาพ container, migration, roles, readiness และ browser flow ทำงานร่วมกันได้บนเครื่องหนึ่ง แต่ staging ยังต้องมี host/registry, secrets, network policy, domain/HTTPS และ database ที่ตั้งใจใช้ การ deploy ต้องผูก image digest กับ source SHA เพื่อรู้แน่ว่ากำลังทดสอบ release ใด

Rollback ไม่ได้หมายถึงย้อน image อย่างเดียว ถ้า schema migration ไม่เข้ากับรุ่นเก่าต้องมีแผน migration แบบ compatible; backup ต้องทดลอง restore ไปฐานใหม่และตรวจข้อมูล ไม่ใช่เพียงมีไฟล์ backup อยู่ รายงานข้อ 18 ระบุว่ายังไม่มีหลักฐานเหล่านี้ จึงไม่ควรติ๊กผ่านจากการเปิดหน้า localhost ได้

### ข้อ 19 — Coverage audit รวบรวมเส้นทางและช่องว่าง

ข้อ 19 เชื่อมข้อกำหนดกับ implementation/test โดยถามว่า flow ทั้งเส้นทางเดินได้หรือไม่: register/login → lesson/progress → exam/submit → Instructor review → feedback หลัง refresh การผ่านบาง API tests แยกกันยังไม่ยืนยันว่าการตั้งค่า Compose, cookie, migration และ UI ต่อกันถูกต้อง

รายงานล่าสุดมี full local run ของ integration, smoke และ browser E2E แต่ยังแยกสถานะชัดเจน: GitHub CI ของ changes ล่าสุดต้องรันบน SHA ใหม่, retake-after-cooldown ต้องมี browser journey, export/accessibility/load audits ต้องทำเพิ่ม และ staging/rollback/restore ยังไม่มี รายการนี้จึงเป็นแผนตรวจช่องว่าง ไม่ใช่ใบรับรองว่า release พร้อมแล้ว

## วิธีอ่านตัวเลขและคำว่า “ผ่าน”

- `passed` คือจำนวน test ที่ผ่านในคำสั่ง/ฐาน/วันที่รายงาน; `deselected` หรือ `skipped` ไม่ใช่ test ที่ผ่าน
- PostgreSQL integration ยืนยันพฤติกรรมกับฐานทดสอบจริง ไม่ได้ยืนยัน production data หรือ hosting
- Browser E2E ตรวจ flow ที่ระบุในรายงาน ไม่ได้ครอบคลุมทุกหน้า, ทุก role หรือ accessibility ทั้งหมด
- GitHub CI ใช้ได้กับ SHA/run ที่ลิงก์ไว้เท่านั้น; ถ้าโค้ดเปลี่ยน ต้องดู run ของ SHA ใหม่
- `local acceptance`, `GitHub CI`, `staging acceptance` และ `production readiness` เป็นคนละระดับ
- รายงานข้อ 14 self-review ทำโดย agent ที่เขียนโค้ด/labels จึงห้ามเรียกเป็น human review อิสระ
- ตัวเลข provider หรือ AI จากรายงานเก่าไม่ใช่ benchmark ของ Dify และห้ามใช้ยืนยันความพร้อมของ Dify

## สรุปช่องว่างสำคัญจากรายงาน

1. **RAG/Dify:** ต้องกำหนด integration contract, secrets, citations/revocation, usage/cost และตรวจคุณภาพกับชุดข้อมูลที่เหมาะสมก่อนเปิดใช้งานจริง
2. **ข้อ 14:** independent human review และ provider usage reconciliation 6 calls ยังไม่ครบในรายงานที่ระบุ
3. **ข้อสอบ:** มี local test ของ retake race/cooldown แต่ยังขาด browser journey ที่เริ่ม retry หลัง cooldown หมด
4. **Operations:** ยังไม่มีหลักฐาน staging, deployment, rollback, backup/restore
5. **การตรวจรุ่นล่าสุด:** ต้องรัน/ดู CI บน SHA ที่จะส่งจริง ไม่เอาผลจาก commit เก่ามาแทน

## รายงานต้นฉบับทั้งหมด

ใช้ลิงก์เหล่านี้เมื่ออยากตรวจรายละเอียด วิธีรัน หรือข้อจำกัดของหลักฐาน:

- [ข้อ 01](step-01-verification.md) · [ข้อ 02](step-02-verification.md) · [ข้อ 03](step-03-verification.md) · [ข้อ 04](step-04-verification.md) · [ข้อ 05](step-05-verification.md)
- [ข้อ 06–10](step-06-10-verification.md) · [ข้อ 07 เพิ่มเติม](step-07-verification.md) · [ข้อ 11](step-11-verification.md) · [ข้อ 11–13 งานค้าง](steps-11-13-follow-up.md)
- [ข้อ 12](step-12-verification.md) · [ข้อ 13](step-13-verification.md) · [ข้อ 14](step-14-verification.md) · [ข้อ 14 agent review](step-14-agent-review.md) · [คู่มือผู้ตรวจข้อ 14](step-14-review-guide.md)
- [ข้อ 15](step-15-verification.md) · [ข้อ 16](step-16-verification.md) · [ข้อ 17](step-17-verification.md) · [ข้อ 18](step-18-verification.md) · [ข้อ 19](step-19-verification.md)
- [รายการสถานะรวม](implementation-checklist.md) · [สารบัญเอกสาร](README.md)

## ภาคผนวก: รายงานต้นฉบับฉบับเต็ม

ภาคผนวกนี้เก็บรายงานต้นฉบับตามเนื้อหาใน repository เพื่อให้ตรวจรายละเอียด วันที่, commit, คำสั่ง, จำนวน test, ข้อจำกัด และหลักฐานอ้างอิงได้โดยไม่ต้องเปิดหลายไฟล์ รายงานเหล่านี้เป็น snapshot ทางประวัติศาสตร์และอาจกล่าวถึง branch, provider หรือสถานะที่ต่างกันตามช่วงเวลา ให้อ่านคำเตือนต้นฉบับของแต่ละรายงาน และใช้คำอธิบาย/ข้อสรุปปัจจุบันในช่วงต้นของเอกสารนี้ประกอบเสมอ เนื้อหาด้านล่างไม่ได้ถูกเขียนใหม่หรือใช้แทนหลักฐานใหม่

### เอกสารต้นฉบับ: [step-01-verification.md](step-01-verification.md)

# ผลตรวจข้อ 01 — 13 ตุลาคม 2026

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


Branch `f1` คงเดิม; HEAD ก่อนเริ่ม `1170066`. ไม่ commit/เปลี่ยน branch/deploy
งานเดิมที่พบ: `docs/README.md` modified และ `docs/implementation-checklist.md` untracked
เก็บเนื้อหาเดิมไว้และเพิ่มผลข้อ 01; ไม่แก้ `prototype/`. ไม่พบ AGENTS.md ใน repository/parent ที่ตรวจ

## สิ่งที่เพิ่ม

- `docs/srs.md`: gaps/conflicts, FR/NFR/use cases/mapping, ER/data deltas,
  training/exam serializer policy, lifecycle/finish/submit, global lock order และ decision register
- `docs/openapi.yaml`: 81 operations (health approved 2, domain draft 79),
  request/response foundations, closed exam views และ requirement IDs;
  domain payload/filter details ที่ยังไม่ครบติดป้าย draft ชัดเจน
- `frontend/`: Next.js App Router/TypeScript landing page, CSS, same-origin proxy,
  standalone build/start scripts, smoke tests, exact package pins/lockfile/env example
- `backend/`: FastAPI health/error envelopes, Python worker entrypoint,
  pinned DB libraries/Alembic, uv lockfile/env example และ foundation/contract tests
- ปรับ API/architecture/database/learning/RAG/scope/index และ root README ให้เชื่อม contract ใหม่
  เพิ่ม runtime version files และ Python/tool cache ignore rules

## ผลที่ตรวจจริง

| Check | ผล |
|---|---|
| npm dependency install/audit | ผ่าน; ชุดสุดท้าย 0 vulnerabilities ใน npm audit |
| npm ci จาก lockfile | ผ่าน (ดูหมายเหตุ runtime ด้านล่าง) |
| uv sync --frozen | ผ่าน; dependencies 50 packages |
| Frontend ESLint / TypeScript | ผ่าน |
| Next.js production build + standalone static assets | ผ่าน |
| FastAPI Uvicorn startup | ผ่านบน 127.0.0.1:8000 |
| Standalone frontend startup | ผ่านบน 127.0.0.1:3000 |
| Backend Ruff check/format + mypy | ผ่าน |
| FastAPI/SQLAlchemy/asyncpg/Alembic import | ผ่าน; ไม่ใช่ DB integration |
| OpenAPI 3.1 validation + approved drift/inventory mapping | ผ่าน |
| pytest | 13 passed; รวม health/error, draft route not exposed, worker exits, contract และ schema leakage guards |
| Frontend HTTP smoke | 3 passed; HTML/JS assets, health 200/ready 503 ผ่าน proxy, domain POST 404 |
| Prototype regression | 18 passed; ไม่แก้ไฟล์ prototype |
| Browser inspection | Edge ผ่าน Playwright runtime ของเครื่อง: 375/768/1440px ไม่มี horizontal overflow, keyboard focus เห็นได้, ไม่มี pageerror; ตรวจ screenshot 375/1440 แล้ว |
| git diff --check | ผ่าน; prototype ไม่มี diff |

Windows sandbox เริ่มต้นทำให้ SWC canonicalize path ไม่ได้และ TestClient ค้าง;
ตรวจซ้ำด้วย approved local execution แล้ว build/tests ผ่าน โดยไม่ได้ลด assertions
Playwright bundled Chromium ไม่มี binary จึงใช้ Edge ที่ติดตั้งอยู่; browser check เป็นการตรวจ local
ครั้งนี้ ไม่ใช่ committed E2E suite หรือหลักฐาน full responsive acceptance ของระบบทั้งหมด
HTTP smoke tests อยู่ใน repository และรันซ้ำตาม getting-started ได้

Starlette test client แจ้ง deprecation เมื่อใช้ HTTPX 0.28.1 (แนะนำ httpx2 ใน upstream รุ่นที่ติดตั้ง)
tests ยังผ่าน; ไม่ suppress warning และยังไม่เปลี่ยน stack HTTPX ตาม docs ในข้อ 01

## สิ่งที่ไม่พร้อม / ไม่ได้อ้างว่าทดสอบแล้ว

DB readiness ตอบ 503 โดยตั้งใจ; ไม่มี DB connection/schema/migration/roles/Compose
หรือ PostgreSQL version/image ที่เลือกแล้ว ไม่มี auth/runner/durable worker/job recovery,
exam/grading/unlock/RAG/real provider, CI/deployment/backup หรือ benchmark จริง
exam allowlist tests ตรวจ draft JSON schema เท่านั้น ไม่ใช่หลักฐาน runtime exam security
ไม่มี default secret หรือ fixture/answer key ถูกคัดลอกเข้า frontend; การตรวจ bundle เป็น smoke
guard ร่วมกับการตรวจ source ไม่ใช่ security scan ครบทั้ง supply chain

ผู้ใช้ยืนยัน policy: Instructor อ่านเฉลยสอบหลัง submit เท่านั้น; learner ได้เฉพาะ rubric feedback
rubric/เกณฑ์ผ่าน, active/retake/expiry policy, override/revoke unlock, feedback disclosure detail,
provider/model/งบ และ hosting ยัง pending ตาม SRS §8
ข้อ 01 ผ่านในฐานะ **contract draft + scaffold** ไม่เท่ากับ SOC-001/002 ทุก phase เสร็จ
หรืออนุญาตให้ทำข้อ 02–19 ต่อโดยอัตโนมัติ

### เอกสารต้นฉบับ: [step-02-verification.md](step-02-verification.md)

# ผลตรวจข้อ 02 — 13 ตุลาคม 2026

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


สถานะ: **ผ่านขอบเขตข้อ 02** รวม Compose execution บน Linux engine จริง
คง branch f1; ก่อนแก้ working tree สะอาด และ fast-forward จาก 65d5562 ไป remote f1 3c952c9
เพื่อรับ README/.gitkeep changes เดิม ไม่แตะ main/prototype และไม่ commit/push/deploy ในงานนี้
ไม่พบ AGENTS.md ใน repository และ parent ที่ตรวจ

## ไฟล์และขอบเขต

- compose.yaml, backend/frontend Dockerfiles และ .dockerignore: DB → bootstrap → migrate → API/worker/web;
  named volume และ test-db tmpfs แยก; pin image versions/digests จาก official registry
- scripts/init-local.py, .env.example, backend/.env.example, .gitignore: สร้าง role passwords สุ่ม
  ไว้เฉพาะ .local; mount แยก credential แต่ละ process ไม่มี default Instructor password
- backend/app/db: config, SQLAlchemy async sessions, privileged bootstrap,
  migration wrapper/ledger/lock, readiness และ provisioning/assignment CLI
- backend/alembic.ini, migrations: initial auth schema 7 app tables + 2 ops tables,
  grants/indexes/constraints; private schema ว่าง; ไม่มี runs/jobs/exam/RAG tables
- app/main.py, app/worker: DB-backed health; worker foundation loop/check ไม่มี queue jobs
- pyproject.toml/uv.lock: SQLAlchemy asyncio extra และ Argon2-cffi 25.1.0
- test_database.py/test_foundation.py, frontend smoke: real DB grants/transactions และ health contract
- docs/openapi.yaml: เปลี่ยนเฉพาะ approved health readiness เป็น 200/503 พร้อม safe models;
  domain inventory 79 operations ยัง draft เช่นเดิม
- frontend landing: บอกสถานะข้อ 02 และเพิ่มลิงก์ readiness; ไม่สร้าง feature auth/exam

## หลักฐานที่รันจริง

| Check | ผล |
|---|---|
| Native DB | EDB PostgreSQL 17.11 Windows binaries; cluster ใน .local/pg-test-data, localhost:55439 เท่านั้น ไม่ติดตั้ง system service |
| Fresh migration | ผ่านบนฐาน soc_test_step02; initial DDL failure rollback ทุกตาราง แล้ว retry สำเร็จ |
| Repeat/concurrent/lock | ผ่าน; advisory lock เดียวกัน, checksum ledger หนึ่ง revision, ไม่ซ้ำเมื่อ migrate พร้อมกัน |
| Drift guard | checksum mismatch ปฏิเสธ migration และ readiness; approved OpenAPI drift tests ผ่าน |
| Runtime permissions | ทดสอบด้วย api/worker/evaluator/retention จริง: ไม่ใช่ owner/superuser, DDL/private/ledger mutation/SET ROLE owner ถูกปฏิเสธ |
| Audit | api/worker/evaluator insert ได้; update/delete/truncate ถูกปฏิเสธ |
| Provisioning | concurrent/repeat ได้ UUID เดียว, mismatch ไม่ทับบัญชี, Argon2 verify ผ่าน, assignment ไม่ซ้ำ/สลับ role ไม่ได้ |
| CLI | สร้าง Instructor ด้วย private random password file สองครั้ง คืน UUID เดียว ไม่มี password ใน output |
| Constraints/session transaction | email/token unique, FK, role/version, nonnegative quota, scope binding, raw token rejection และ rollback ผ่าน |
| Backend suite | 29 passed = 16 PostgreSQL integration + 13 foundation; 1 upstream HTTPX test-client deprecation warning |
| Static/dependencies | Ruff app/tests/migrations/scripts, mypy app และ uv sync --frozen --offline ผ่าน; git diff --check ผ่าน |
| Readiness | API ใช้ api_runtime, worker ใช้ worker_runtime; DB/head/checksums ถูกให้ ready; credential ไม่ตรงปฏิเสธ |
| Restart persistence | หยุด/เริ่ม PostgreSQL จริง; user IDs, session/challenge counts, migration revisions snapshot ตรงเดิม |
| Failure/recovery smoke | ระหว่าง DB หยุด API readiness 503; หลัง restart frontend proxy readiness 200 |
| Frontend | ESLint/typecheck/production build ผ่าน; HTTP smoke 3 passed กับ API+PostgreSQL จริง |
| Worker process | เริ่มและรายงาน database_ready=true, queue_ready=false; ไม่มี runner/job handlers |
| Compose | Docker Desktop 4.95.0, Engine 29.8.2 linux/amd64, Compose 5.6.0; config/build/up --wait ผ่านบน named volume ใหม่ |
| Docker images | pinned Python/Node/PostgreSQL images pull/build/run ผ่าน; API/worker UID 10001 และ frontend UID 1000 ไม่ใช่ root |
| Container integration | test profile: 16 passed, 1 upstream warning; test-db เป็น tmpfs แยกจาก soc named volume |
| Container frontend | HTTP smoke 3 passed ที่ localhost:3000; assets/proxy/readiness และ draft route 404 ผ่าน |
| Container provisioning | private random password file mount read-only; รันซ้ำได้ UUID เดิม ไม่พิมพ์ password |
| Container persistence | หยุด DB แล้ว readiness 503; down/up โดยไม่ลบ volume แล้ว user UUID/email/role, migration checksum และ audit count ตรงเดิม; readiness กลับ 200 |
| Final services | db/api/worker/frontend healthy; bootstrap/migrate exit 0; หยุด test-db หลังทดสอบ |

Frontend build ครั้งแรกติด EBUSY เพราะ standalone server จากข้อ 01 ถือ directory อยู่
หยุดเฉพาะ process ที่เปิดไว้ใน chat นี้แล้ว build ผ่าน ไม่ลบงานผู้ใช้หรือแก้ test ให้ผ่านผิด ๆ
เริ่ม native API/UI สำหรับ smoke ที่ 8002/3002 เพื่อเลี่ยง service เดิม ส่วน Compose ใช้ 8000/3000

## ประวัติ blocker และผลตรวจต่อ

รอบแรก `docker compose build` ล้มเพราะไม่มี Docker daemon pipe (`docker_engine` not found)
เมื่อกลับมาทำต่อ พบ Docker Desktop ติดตั้งแล้วและ engine พร้อม จึงไม่ได้ติดตั้งซ้ำ
ตรวจ Linux build, secret mounts ภายใต้ non-root users, startup บน volume ใหม่,
integration/provisioning และ named-volume persistence ผ่านครบแล้ว คำสั่งสำหรับรันซ้ำ:

```powershell
python scripts/init-local.py
docker compose up --build -d
docker compose ps -a
docker compose --profile test run --build --rm test
docker compose restart db
# ตรวจ readiness และข้อมูลบัญชีที่ provision ยังอยู่
```

ใช้ [คู่มือ](local-development.md) สำหรับ ports/provisioning/test isolation และ shutdown
ยังไม่มี auth UI/API, CI (ข้อ 03), durable jobs/heartbeat/runner (ข้อ 06), pgvector,
provider/exam/grading/deployment/backup. ไม่เลือก rubric/override/retake policy เพิ่ม
PostgreSQL 17 เป็น local baseline; production hosting และ major/extension compatibility ยัง pending
รายงานข้อ 01 เป็นประวัติผลเดิม ส่วน readiness/worker ปัจจุบันใช้พฤติกรรมข้อ 02

### เอกสารต้นฉบับ: [step-03-verification.md](step-03-verification.md)

# ผลตรวจข้อ 03 — 13 ตุลาคม 2026

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


สถานะ: **ผ่าน local และ GitHub CI; branch protection ติดข้อจำกัดแพ็กเกจ**
เริ่มงานบน f1 ที่ 3c952c9 พร้อมงานข้อ 02 ที่ยังไม่ commit; คงงานเดิมไว้ครบ ไม่ switch/reset/stash
ตรวจไม่พบ AGENTS.md; remote HEAD เป็น main ต่อมาผู้ใช้อนุญาต commit/push/PR และตรวจ CI จริง ผลอยู่ด้านล่าง

## ไฟล์ที่เพิ่ม/แก้เฉพาะข้อ 03

- .github/workflows/ci.yml: prototype/backend/frontend/integration/ci-gate, SHA pins, read-only token, report artifacts
- scripts/ci_gate.py และ scripts/tests/test_ci.py: fail-closed result aggregation และ regression
- scripts/ci-compose.sh: disposable Compose project, integration/HTTP smoke และ cleanup ของ project นั้น
- scripts/check-doc-links.py: local Markdown file targets; .gitattributes: shell scripts ใช้ LF
- docs/ci-local.md, ci-cd.md, README/index/checklist และรายงานนี้: วิธีรันและ pending GitHub evidence

ไม่มี API/UI/migration ใหม่ในข้อ 03 เพราะขอบเขตคือ CI ของ implementation ที่มีแล้ว
ไม่เปลี่ยน policy สิทธิ์/คะแนน/providers; full deployment design ใน ci-cd.md เป็นอนาคตตาม checklist 18

## ผลรันจริง

| Check | ผล |
|---|---|
| prototype | node syntax 3 files + 18 tests ผ่าน |
| backend | uv frozen install, Ruff lint/format, mypy ผ่าน; foundation/approved OpenAPI 13 tests ผ่าน |
| gate | 4 unittest methods ผ่าน รวม failure/cancelled/skipped/missing/malformed และ CLI exit codes; needs ครบทุก job |
| workflow | actionlint 1.7.7 checksum verified; syntax/expressions และ bash -n ผ่าน |
| docs | local Markdown file targets ผ่าน |
| frontend | npm ci/lint/typecheck/production build ผ่าน |
| exact CI integration script | Git Bash + Docker Linux Engine, project soc-ci-local03: build/up/migrate ผ่าน |
| PostgreSQL integration | 16 tests ผ่านใน test container, JUnit integration.xml เขียนได้ด้วย non-root |
| HTTP/worker | frontend smoke 3 tests ผ่าน; worker database_ready=true และ queue_ready=false |
| cleanup | script ลบ soc-ci-local03 containers/network/volume แล้ว; soc-local ยังทำงาน; ทดลองชื่อ soc-local ถูกปฏิเสธ exit 2 ก่อนเรียก Docker |
| reports | backend.xml/integration.xml อยู่ใน ignored test-results; GitHub artifact upload ผ่านใน run ที่อ้างอิงด้านล่าง |

Backend มี upstream HTTPX/Starlette deprecation warning เดิม 1 รายการ ไม่ suppress และไม่มี test failure
พบ format mismatch ใน script ระหว่างรอบแรก แก้ให้ใช้ backend Ruff config แล้วตรวจผ่าน
ไม่มี dependency/runtime upgrade หรือเปลี่ยน lockfilesเพิ่มจากงานข้อ 02

## GitHub verification ที่รันจริง

- Commit 3dfb57b เก็บงานข้อ 02/03; 13cbf3a รวม ancestry ของ main ที่เคย revert scaffold โดยคง f1 tree เพื่อให้ PR มีระบบครบ ไม่แก้ main
- [PR #3](https://github.com/IMLV1/SOC/pull/3) f1 → main ถูก merge จาก GitHub ระหว่างการบันทึกหลักฐาน โดย agent ไม่ได้สั่ง merge; merge SHA d9a92de1bf902f49e230d159d809bc96b0a965a4
- [รอบแรก](https://github.com/IMLV1/SOC/actions/runs/38395949531): prototype/frontend/integration ผ่าน; backend ล้มใน import smoke และ ci-gate ล้มตามจริง
- แก้ import smoke ให้ใช้ alias api (import worker เคย bind ชื่อ app ทับ FastAPI instance) ใน commit 12bedb6; ไม่ใช่ test assertion ที่ถูกลดความเข้มงวด
- [รอบผ่าน](https://github.com/IMLV1/SOC/actions/runs/38396418296), SHA 12bedb63dff11da98e262452bb87650dd68a124b: prototype/backend/frontend/integration/ci-gate success ทั้งหมด รวม setup/cache/artifact steps
- [PR ทดสอบ #4](https://github.com/IMLV1/SOC/pull/4) ใช้ branch แยก ไม่แก้ f1; [run](https://github.com/IMLV1/SOC/actions/runs/38396064683) สั่ง cancel แล้ว conclusion=cancelled, integration=cancelled, ci-gate=failure
- PR #4 มี deliberate failing test แต่ backend หยุดที่ import-smoke bug ก่อนถึง test นั้น จึงไม่อ้างว่า deliberate test ถูก execute; หลักฐาน failure propagation ใช้รอบแรกของ PR #3
- ปิด PR #4 โดยไม่ merge และลบ temporary branch แล้ว; ยังเก็บ run URLs สำหรับตรวจย้อนหลัง
- เจ้าของมี admin permission แต่ GET main/protection และ rulesets ตอบ HTTP 403: "Upgrade to GitHub Pro or make this repository public to enable this feature." ไม่แก้ visibility/ซื้อแพ็กเกจเอง

## ยังไม่ยืนยัน

- fork/merge_group event จริง (workflow รองรับและ syntax ผ่าน แต่ทดสอบครั้งนี้ใช้ PR ใน repo เดียวกัน)
- branch protection/ruleset และ enforced merge blocking เมื่อ failure/cancelled: ติด GitHub plan ไม่ใช่ CI ผ่านแล้วแปลว่า protection เปิด
- ไม่มี domain E2E/generated client, security scan เต็มระบบ, provider หรือ deploy จนกว่าจะถึงงานที่กำหนด

ดู [คำสั่ง local และขั้นตั้ง required check](ci-local.md)

### เอกสารต้นฉบับ: [step-04-verification.md](step-04-verification.md)

# ผลตรวจข้อ 04 — 14 ตุลาคม 2026

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


Branch `codex/step-04-auth` สร้างจาก origin/main `56b49a9` หลัง PR #5 merge
ก่อนเริ่ม working tree สะอาด ไม่พบ AGENTS.md; คง prototype และงานข้อ 01–03
ผู้ใช้ยืนยัน registration defaults 10 runs/20 AI requests ต่อวัน UTC แก้เฉพาะการตัดสินใจนี้

## ไฟล์ที่เปลี่ยน

- backend/app/auth: request/response models, session/CSRF/Argon2id, quota/read models, rate limit และ owner/assignment policies
- backend/app/demo.py: public benign snapshot; http_models.py/main.py: shared safe envelopes/routers/errors
- migrations/versions/0002_auth_rate_limits.py: counters/grants โดยไม่แก้ migration 0001 ที่เคยใช้แล้ว
- backend/tests/conftest.py: shared isolated DB fixtures; test_auth.py และ test_database.py: behavior/races/upgrade
- frontend/src/app: login/register/account/demo และ session-aware navigation; lib: API fetch และ generated DTOs
- frontend/tests/browser/auth.spec.ts, playwright.config.ts, package.json/package-lock.json: Chromium regression
- compose.yaml/backend env/Dockerfile, CI workflow/script: local cookie/origin config และ auth/browser tests
- docs/openapi.yaml, SRS/API/architecture, checklist/คู่มือ และ type-generation script

## ผลตรวจจริง

| Check | ผล |
|---|---|
| PostgreSQL integration | 26 passed: DB เดิม 16 + auth 9 + upgrade จาก 0001 อีก 1 |
| Auth | register ไม่ auto-login; normalized email; role/quota injection ถูกปฏิเสธ; login failure generic; opaque/hash-only session; rotation/logout |
| Security regression | Origin/CSRF/replay/expired challenge; session expiry/revoke/disabled; Secure/HttpOnly/SameSite; 429 หลัง failed attempts |
| Isolation | /me เลือกบัญชีจาก cookie ไม่ใช้ query user_id; owner mismatch 404; Instructor นอก assignment 404; Analyst admin policy 403 ผ่าน api_runtime |
| Concurrency/upgrade | สมัคร email เดียวพร้อมกันได้ 201/409 และมี user/quota/audit อย่างละ 1; upgrade เก็บบัญชีจาก 0001 |
| Foundation/contract | 13 passed; approved FastAPI paths/schema เทียบ OpenAPI และ draft exam allowlists ยังผ่าน |
| Browser Chromium | 2 E2E ผ่าน: register→login→refresh→logout ผ่าน Next.js proxy; stale session response ไม่ทำให้ UI กลับมา login หลัง logout; Guest demo read-only; widths 375/768/1440 ไม่ overflow |
| HTTP smoke | 3 passed; assets/proxy และ domain routes ที่ยังไม่ implement ยัง unavailable |
| Build/static | Docker Next standalone build, frontend lint/typecheck, backend Ruff/format/mypy และ actionlint ผ่าน |
| CI scope | เพิ่ม auth integration, Chromium และ generated DTO drift checks; GitHub CI ผ่านทั้ง 5 jobs บน commit `ea59c0e` ตามหลักฐานด้านล่าง |

Backend ยังมี upstream HTTPX/Starlette deprecation warning เดิม ไม่ suppress
ชุด integration/CI ใช้ project soc-ci-auth04 และฐานแยก ไม่แตะข้อมูลผู้ใช้จริง
การตรวจข้ามบัญชีเป็น account projection และ authorization policy ของข้อ 04;
ยังไม่อ้างว่า run/ticket/admin endpoints ที่ไม่มีอยู่ถูกทดสอบแล้ว

## ยังไม่พร้อม / นอกขอบเขต

ยังไม่มี scenario/runner, lessons/exam, admin CRUD, email verification/password reset, provider หรือ public deployment
ส่วน demo ticket/alert/evaluation ยัง draft; ข้อนี้ให้ตัวอย่างอ่าน request/response เท่านั้น
Production ต้องใช้ HTTPS Secure cookies, trusted proxy/rate-limit policy และ retention scheduler ตามงานถัดไป
branch protection ยังติด GitHub plan เดิม; ไม่เปลี่ยน billing/visibility
ส่งงานใน [PR #6](https://github.com/IMLV1/SOC/pull/6); ยังไม่ deploy; วิธีเปิดและคำสั่งตรวจอยู่ใน [คู่มือ auth](auth-development.md)
เปิด preview project soc-auth04 แยกที่ localhost:13004 (API 18004, DB 55434); ไม่มี provider จริง

## หลักฐาน GitHub CI

[Run 38482432510](https://github.com/IMLV1/SOC/actions/runs/38482432510)
ตรวจ commit `ea59c0e851d0736336c7bece2cfd8307df00a097` ใน PR #6 แล้วสำเร็จ:
backend, frontend, prototype, integration และ ci-gate ผ่านทั้งหมด
Integration รัน PostgreSQL tests 26, HTTP smoke 3 และ Chromium E2E 2 จริงบน GitHub
การแก้เอกสารเพื่อบันทึกผลนี้จะกระตุ้น CI รอบใหม่; ดูผลของ PR head ล่าสุดในหน้า Checks
ผล CI ไม่ได้หมายความว่าตั้ง branch protection แล้ว: ข้อจำกัดแพ็กเกจเดิมยังอยู่

### เอกสารต้นฉบับ: [step-05-verification.md](step-05-verification.md)

# ผลตรวจข้อ 01 ทบทวน / ข้อ 05 — 14 ตุลาคม 2026

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


เริ่มจาก working tree สะอาดบน codex/step-04-auth; fetch แล้ว main เป็น 6a51b51 หลัง PR #7 merge
สร้าง branch codex/step-05-scenarios จาก main เพื่อแยกงานใหม่ ไม่แก้ prototype/หรือลดงานข้อ 02–04
ไม่พบ AGENTS.md; อ่าน docs รวม learning-path/RAG และตรวจ contract inventory ก่อนแก้

## ทบทวนข้อ 01

SRS/OpenAPI/mapping, App Router/TypeScript, FastAPI/worker, runtime pins, lockfiles,
.env.example และ health มีอยู่แล้ว คงเวอร์ชันที่ตรวจจริงไว้ ไม่สร้าง scaffold ทับ
แก้ข้อความสถานะล้าสมัยที่ยังบอกว่าเปิด health เท่านั้น/ยังไม่มี auth/DB
boundary/lifecycle/finish-submit/lock order ยึด SRS; ไม่มีการเปลี่ยนสิทธิ์/คะแนน/ผลิตภัณฑ์
rubric, retake/active attempt, override/revoke unlock, feedback disclosure, provider และ hosting ยัง pending

## ขอบเขตข้อ 05

เพิ่ม scenario models/loader/seed/catalog/exam policy, migration 0003,
S01–S05 training fixtures + private truth, Docker artifact separation,
catalog UI/generated DTO และ regression tests/CI พร้อม [คู่มือ](scenario-development.md)
S02 เปิดใน catalog; อีก 4 แบบเตรียม schema/events/truth แต่ยัง disabled
ไม่สร้าง jobs/run controls/detector/exam bank/grading/provider/deploy

## ผลตรวจ

| Check | ผลที่รันจริง |
|---|---|
| Foundation/contract/fixture policy | 20 passed; OpenAPI valid, approved paths/schema drift, draft route denial และ exam projection tests |
| PostgreSQL integration | 30 passed บน roles จริง รวม auth/DB เดิม; fresh migration, upgrade จาก 0001 และ 0002 รักษาบัญชี |
| Container test command | 37 passed = integration 30 + fixture/policy unit 7 (unit 7 ซ้ำกับชุด 20; รวม backend ไม่ซ้ำ 50) |
| Seed | 5 versions/10 groups, repeat/concurrent ไม่ duplicate; conflict rollback; exam purpose ปฏิเสธที่ loader/seed/DB |
| Grants/admission | API/worker SELECT truth ไม่ได้; evaluator อ่านได้แต่แก้ไม่ได้; API อ่าน hashes/เขียน catalog ไม่ได้; disabled/unknown/demo UUID ไม่ผ่าน training selector |
| API/errors | catalog มีแต่ allowlisted metadata, cursor/limit validation และ pagination ไม่ซ้ำ; fixture paths 404, run/attempt creation ยัง 404; errors ไม่ echo input |
| Artifact isolation | container API ไม่มี fixtures, worker มีเฉพาะ training events ไม่มี catalog/truth, web ไม่มี backend; browser JS ทุกไฟล์ผ่าน leakage test 1 |
| HTTP/worker | smoke 3 passed; database_ready=true, queue_ready=false |
| Browser | Chromium E2E 4 passed: auth/Guest เดิม + catalog ที่ 375/768/1440 ไม่มี overflow + loading/error/retry/empty |
| Static/build | Ruff lint/format (38 files), mypy (23 source files), frontend lint/typecheck/standalone build, actionlint, doc links, DTO drift และ gate regression 4 ผ่าน |
| Reproducibility | uv sync --frozen --offline ผ่าน; runtime/package lockfiles เดิมไม่เปลี่ยน; Docker build ใช้ pinned images/dependencies |
| CI local | scripts/ci-compose.sh exit 0 ใน project soc-ci-scenarios05, cleanup เฉพาะ test project/volume สำเร็จ |

ยังมี upstream HTTPX/Starlette deprecation warning เดิม ไม่ suppress และไม่ลด assertions
prototype ไม่มี diff; ไม่อ้างว่ารัน prototype regression ใหม่ในข้อนี้

## เปิดตรวจและสิ่งที่ยังไม่พร้อม

Preview แยก project soc-scenarios05: [catalog](http://127.0.0.1:13005/scenarios),
[API](http://127.0.0.1:13005/api/v1/scenarios), API port 18005, DB port 55435
เปิดซ้ำด้วย SOC_WEB_PORT=13005, SOC_API_PORT=18005, SOC_DB_PORT=55435 แล้ว
`docker compose -p soc-scenarios05 up --build -d --wait`; หยุดด้วย down โดยไม่ลบ volume

ข้อ 05 ผ่าน local acceptance; เพิ่ม regression tests ใน CI แล้ว แต่ **รอยืนยันบน GitHub**
ยังไม่ commit/push งานข้อ 05 ไม่ deploy ภายนอกและไม่เปิด provider
exam policy ตรวจเฉพาะ helper + schema/route denial ไม่ใช่ end-to-end exam/lesson gate ที่ยังไม่มี
S01/03/04/05 ยัง disabled; detector acceptance อยู่ข้อ 08, runner อยู่ข้อ 06
rubric/retake/unlock/provider ตาม decision register ยัง pending และ branch protection ยังติดแพ็กเกจเดิม

### เอกสารต้นฉบับ: [step-06-10-verification.md](step-06-10-verification.md)

# ผลตรวจข้อ 06–10 (อัปเดต 15 ตุลาคม 2026)

> **หมายเหตุสถานะปัจจุบัน:** การกล่าวถึง Gemini ในเอกสารนี้เป็นข้อมูลย้อนหลัง/หลักฐานของ implementation ก่อนเลือก Dify ไม่ใช่คำสั่งให้เปิดใช้หรือสถานะ provider ปัจจุบัน; repository ต้องใช้ Dify API เท่านั้น และ runtime ยังปิดจน integration ผ่านการตรวจรับ

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


## Audit ล่าสุด — สถานะนี้มีผลเหนือรายงานรับงานเดิมด้านล่าง

### ปิด acceptance ข้อ 08 — 14 ตุลาคม 2026

- Rules/anomaly/correlation v2 ตรึง config ไว้ใน `run_versions`; run ที่ตรึง v1 ยังคงใช้ policy v1 เพื่อรักษาผลย้อนหลัง
- Rules ใช้ failed login ≥10/5 นาที, scanner ≥4/5 นาที และแสดง blocked request เป็นหลักฐาน low severity โดยไม่สรุปว่าถูกเจาะ
- Anomaly ใช้ baseline ที่ปล่อยแล้ว, อย่างน้อย 3 read events ใน 60 วินาที และ ≥8 เท่าของ baseline (`baseline_reads_per_minute × 100 records/read`); S05 สร้าง anomaly จริง
- Correlation จำกัด scenario instance/account/session/asset/time; detector query อ่านเฉพาะ released events ของ run นั้น
- Integration tests ส่ง duplicate detection jobs สองงานซ้ำแล้ว detection/alert/automatic ticket ไม่เพิ่ม; เมื่อ S05 มีหลักฐานใหม่หลัง soft-delete จะได้ detection/alert revision ใหม่ที่ผูก ticket เดิม ไม่มี ticket ซ้ำ และ FK ปฏิเสธ detection/ticket evidence ข้าม run
- Chromium E2E บน S02 รอ alert และ automatic ticket ที่สร้างจาก PostgreSQL จริง; alerts แสดง severity, version, explanation, evidence count และ link ไป ticket
- Normal traffic และ fixtures S01–S05 ผ่าน unit cases; blocked request ไม่ถูกตีความเป็น successful compromise
- ผล local: integration 45 passed, HTTP smoke 3 passed, Chromium 9 passed; หลังเพิ่ม S05 PostgreSQL flow และปรับ correlation ล่าสุด รัน duplicate-job/S05 integration ซ้ำ 2 passed. Unit detector 2 passed, Ruff, mypy 50 modules, generated DTO drift, frontend lint/typecheck และ diff check ผ่าน
- รอบ Docker full CI ถัดจากเพิ่ม S05 test ติดดาวน์โหลด dev dependencies จึงยุติและล้าง project; S05 กับ duplicate-job tests รันแยกบน PostgreSQL disposable แล้วผ่าน. GitHub CI ของ working changes ยังรอยืนยัน

### Acceptance runner continuity ที่รันจริงเพิ่มเติม

14 ต.ค. 2026: `node frontend/tests/runner-continuity.cjs` exit 0
บน Compose soc-accept06 แยก UI/API/DB ports 13006/18006/55436
Chromium สมัคร/login บัญชี synthetic แล้ว POST S02 ผ่าน same-origin API (201)
run_id 7bbb7378-6032-409c-bcfa-7badd03dad1a:

| จุดตรวจ PostgreSQL | สถานะ | Events | Unique event keys / release_seq | Jobs / unique dedupe keys |
|---|---|---|---|---|
| เริ่ม S02 | running | 1 | 1 / 1 | 3 / 3 |
| หลัง logout 204 และ /me 401 | running | 2 | 2 / 2 | 5 / 5 |
| หลังปิด Chromium ทั้ง process | running | 3 | 3 / 3 | 7 / 7 |
| หลัง restart worker จน schedule จบ | reviewing | 15 | 15 / 15 | 37 / 37 |

**เกณฑ์ย่อย API→released events, logout/browser close ไม่หยุด runner และ restart ไม่ซ้ำผ่านจริง**
ไม่ได้เร่ง/แก้ elapsed clock ใน DB; ไม่สร้าง evaluation score
JSON หลักฐาน local อยู่ ignored test-results/runner-continuity.json ไม่มี passwords/cookies/key
คำสั่งตรวจซ้ำต้องเปิด disposable project soc-accept06 ตาม ports นี้ก่อน และตั้ง SOC_DOCKER_BIN
ถ้า Docker CLI ไม่อยู่ PATH; script สร้างบัญชีทดสอบใหม่ทุกครั้ง ไม่ใช้ production
ผล continuity ครั้งแรกนี้ถูกตรวจซ้ำกับ worker ที่แก้ fencing แล้วตามหลักฐานเพิ่มเติมด้านล่าง

ตรวจโค้ด HEAD 2cc275f พร้อม working changes ที่ยังไม่ commit
local CI รอบล่าสุด soc-ci-pending1113: PostgreSQL integration 39 ผ่าน, HTTP smoke 3 ผ่าน,
Chromium E2E 5 ผ่าน รวม run start/evidence/pause/refresh/resume และ 375/768/1440
จึงยืนยัน Playwright CLI ได้แล้ว; ข้อความเดิมที่บอกว่ายังไม่รันเป็นประวัติ
รอบ audit นี้ backend non-integration 37 ผ่าน (รวม foundations งานถัดไป), Ruff/format/mypy,
approved OpenAPI/schema และ generated DTO drift ผ่าน; frontend lint/typecheck ผ่าน
ไม่ได้อ้างว่ารัน GitHub CI ของ working changes แล้ว

| ข้อ | ผลตรวจรับปัจจุบัน | ช่องว่าง |
|---|---|---|
| 06 | ผ่าน local acceptance หลังแก้ | เพิ่ม test_worker_fencing.py ตรวจ contention จริงทั้งสองลำดับ, expired/reclaimed lease, stale analysis result และ transaction rollback; ทุก domain handler จับ run ก่อน job/resource; recovery แยกจาก claim |
| 07 | Local vertical slice ผ่าน | Chromium CLI start/evidence/pause/refresh/resume/responsive ผ่านจริง; ไม่ใช่ acceptance ระบบทั้งหมดหรือผล GitHub ของ working changes |
| 08 | ผ่าน local acceptance ตามผลตรวจล่าสุดด้านบน | Run ใหม่ใช้ rules-v2/baseline-v2/correlation-v2 และ frozen config; integration, anomaly S05, duplicate jobs, cross-run FK และ UI alert ผ่าน local; GitHub CI รอยืนยัน |
| 09 | ผ่าน local acceptance ตามผลตรวจล่าสุดด้านล่าง | disposition คง 3 ค่า (`true_positive`, `false_positive`, `undetermined`) ตามข้อสรุปผู้ใช้; `benign_positive` ยังไม่เปิดเพราะ scoring contract ยังไม่กำหนด |
| 10 | Mock และ real local acceptance ผ่าน; Gemini Free Tier S02 Chromium E2E และ migrations 0008–0009 วันที่ 15 ต.ค. | PostgreSQL timeout/invalid output/retry/quota/citation/evidence tests ผ่าน; global token/cost caps, 429 policy และ experiment C ยัง pending |

Audit แรกปรับ 06/08/09 เป็น pending; หลังแก้และตรวจเพิ่ม 06/08 ผ่าน local และข้อ 09 ผ่าน local acceptance ตามข้อสรุป disposition ล่าสุด; 07/10 คง local acceptance
ผล tests ผ่านไม่ใช้แทนการตรวจ requirement coverage และไม่ปรับกฎ/คะแนนแทนผู้ใช้ใน audit นี้

กิ่ง `codex/steps-06-10` เริ่มจาก `origin/main` ล่าสุด ณ วันที่ทำงานนี้ ไม่แตะ `prototype/` และไม่ deploy/push ภายนอก การทดสอบฐานข้อมูลใช้ `test-db` แบบ tmpfs; การทดสอบ UI ใช้ Compose project แยก `soc-verify-steps` บน loopback 4300/8400/55433 ไม่ใช้ฐานข้อมูลของ project เดิม

## ผ่านและตรวจรับแล้ว

- **06:** Alembic 0004 สร้าง runs/instances/versions/events/jobs/idempotency; worker ใช้ PostgreSQL clock, lease, fencing, retry สูงสุด 3 ครั้ง และ recovery ของ run ที่ไม่มี wake-up. Integration ทดสอบ start พร้อมกัน, idempotency/quota, crash ก่อน/หลัง domain commit, pause/resume และ resume ที่ยังไม่มี event ใหม่. Browser login แล้วเริ่ม S02 จริง, logout และ restart worker: run เดิมจบ schedule เป็น `reviewing`, มี 15/15 released events และ release_seq ซ้ำ 0. `finish` คงสถานะ `completing` พร้อม cutoff/job; ยังไม่มีผลคะแนน เพราะ evaluator เป็นข้อ 11.
- **07:** Next.js run list/start และ Event explorer ใช้ API จริง มี polling/backoff, source filter, after_seq/cursor และ request/response/log แสดงเป็น escaped text. Chromium Playwright CLI เดิน login → start S02 → อ่าน event → pause → refresh → resume และตรวจ viewport 375/768/1440 ว่าไม่มี horizontal overflow; รอบล่าสุด flow เดียวกันเปิด real provider และเห็น analysis สำเร็จ.
- **08:** Alembic 0005 และ worker detector สร้าง versioned rule/anomaly/correlation, evidence, alert และ automatic ticket. Tests ครอบ S01–S05, normal page view, S05 anomaly, blocked request ไม่สรุป compromise สำเร็จ, rerun detector ไม่เพิ่ม detection และ soft-deleted automatic ticket ไม่ถูกสร้างซ้ำ. DB composite FK ปฏิเสธ evidence ข้าม run. Browser S02 เห็น alert/ticket/mock analysis จากข้อมูลที่ปล่อยจริง.
- **09:** Alembic 0006 เพิ่ม Ticket/Note CRUD, assessment revisions, note versions/evidence, audit และ expected_version. PostgreSQL integration 6 tests ครอบ owner/Instructor assignment และ Instructor PATCH, cross-run refs, deleted parent, 409 version conflict, completing read-only, ticket timeline และ filters/cursor. Playwright E2E ผ่านบน Compose แยก: สร้าง manual ticket จาก event จริง, เปิดสองแท็บให้เกิด 409 โดย draft ยังอยู่หลัง refresh latest, สร้าง assessment revision, เลือก note evidence และยืนยัน edit history. Ticket API/OpenAPI ใช้ disposition 3 ค่า (`true_positive`, `false_positive`, `undetermined`) ตามข้อสรุปผู้ใช้; `benign_positive` ยังไม่เปิดเพราะ scoring contract ไม่ได้กำหนดผลไว้.
- **10:** Alembic 0007–0009 เพิ่ม analysis/provider mode, frozen evidence refs, attempts, async job, citation subset validation, quota reservation/reconciliation, GET/retry และ list filter/cursor; migration 0008 ถอนสิทธิ์ worker แก้ released events และ 0009 อนุญาต pin `real`. Mock deterministic tests ยังผ่าน. Gemini Free Tier adapter ใช้ Gemini 3.5 Flash-Lite เฉพาะ synthetic S02; structured output ผ่าน Pydantic/citation validation, usage tokens ถูกบันทึก และ malformed response ที่มี usage ถูกคิด quota. timeout ของ real provider คง reservation `unknown`. Chromium E2E ผ่าน login → S02 → real analysis `succeeded` → event explorer → pause/resume; DB ยืนยัน mode/model `real`/`gemini-3.5-flash-lite`, usage 2,615 tokens และ reservation consumed. key อยู่ Docker secret ที่ mount ให้ worker เท่านั้น; frontend ไม่มี secret. PostgreSQL/unit 76 passed, foundation/contract 13 passed, Ruff/format/mypy 51 modules, frontend lint/typecheck, Linux production build และ real E2E 1 passed. GitHub CI ของ working changes รอยืนยัน; ข้อ 12 ยังไม่ผ่าน global caps/429/experiment C และข้อ 13 RAG/embedding ยัง pending.

## ยังไม่พร้อมหรือยังไม่ได้ตรวจ

- Investigation Playwright E2E รันผ่านบน Compose แยกโดยใช้ Chrome ที่ติดตั้งในเครื่องผ่าน `PLAYWRIGHT_EXECUTABLE_PATH`; ใช้ config เดิมของ CI ได้โดยไม่ตั้งตัวแปรนี้เมื่อมี browser ของ Playwright ติดตั้งแล้ว.
- ณ เวลาตรวจข้อ 06–10, `finish` ยังรอ evaluator จึงไม่มี evaluation snapshot; งานนี้เสร็จในข้อ 11 ตาม [ผลตรวจแยก](step-11-verification.md). RAG/embedding, experiment C และ global token/cost controls ยัง pending.
- ยังไม่ได้ deploy, publish, push หรือเปิด paid provider. Compose verification stack เป็น local loopback/ฐานข้อมูลแยกเท่านั้น; real request ที่ทำใช้ synthetic data บน Free Tier ที่ผู้ใช้ยืนยัน.

## คำสั่งตรวจซ้ำ

1. `python3 scripts/init-local.py` (สร้าง secrets เฉพาะเมื่อยังไม่มี)
2. `docker compose --profile test up -d test-db`
3. `docker compose --profile test run --rm test` (หลัง build test image ใหม่)
4. `docker compose build frontend` และ `docker run --rm soc-frontend-check:local npm run lint` หลัง build stage image สำหรับ lint
5. `docker run --rm -v "$PWD:/repo:ro" -w /repo/backend -e PYTHONPATH=/repo/backend soc-local-test:latest python -m pytest tests/test_foundation.py -q -p no:cacheprovider`
6. สำหรับเว็บจริงใช้ Compose project/ports แยก เช่น `SOC_DB_PORT=55433 SOC_API_PORT=8400 SOC_WEB_PORT=4300 docker compose -p soc-verify-steps up -d --build` แล้วเปิด `http://127.0.0.1:4300/runs` (อย่าใช้ project/ports นี้พร้อมข้อมูลเดิมโดยไม่ตรวจ).

ผลล่าสุดก่อน audit ข้อ 10: backend integration **48 passed**, foundation/contract **13 passed** และ generated API types `--check` ผ่าน; Ruff, Mypy, Next.js production build, frontend lint และ HTTP smoke **3 passed**. รอบยืนยันข้อ 10 นี้รัน pipeline integration **7 passed**, unit **4 passed**, Chromium S02 E2E **1 passed**, frontend lint/typecheck และ production build ผ่าน. มีเพียง warning ของ Starlette/TestClient dependency ที่ไม่ทำให้ test ล้ม. Auth rate-limit test ตรึงเวลาใน test เพื่อไม่ให้ข้าม bucket ระหว่างนาที.

## จุดไม่ตรงกันใน docs และข้อสรุปที่ใช้

`database.md` §migration outline ยังเรียก events/detection ว่า revision `003` แต่ revision `0003_scenario_catalog` ถูกใช้ไปแล้วในข้อ 05. จึงต่อ Alembic เป็น `0004`–`0007` แบบ append-only ไม่แก้ migration เดิม; ควรปรับ outline ให้ตรงกับ migration ที่ใช้งานจริงในรอบเอกสารต่อไป. `api.md` ระบุ list filters/cursor และ timeline กว้างกว่าข้อความย่อใน checklist; รอบนี้ implement และทดสอบส่วนของข้อ 09/10 ที่เกี่ยวข้อง แทนการตัด contract. ไม่มีการเลือกเปลี่ยนสิทธิ์/คะแนน/ขอบเขตผลิตภัณฑ์เอง.

## ปิด acceptance ข้อ 06 — 14 ตุลาคม 2026

- เปลี่ยน app/worker/jobs.py และ fencing.py: run lock ก่อน job; recovery แยก transaction จาก claim; settle/heartbeat ปฏิเสธ expired token
- detection/analysis worker ตรวจ lease ก่อนเขียนและก่อนจบ domain transaction; analysis provider call อยู่นอก transaction
- test_worker_fencing.py เพิ่ม 6 integration cases: pause-first/release-first contention ตรวจด้วย pg_stat_activity; expired/replaced worker; stale analysis output หลัง network; rollback เมื่อ lease หมดกลาง transaction
- Local CI soc-ci-fencing06 exit 0: PostgreSQL integration 45 passed, HTTP smoke 3 passed, Chromium E2E 5 passed และ cleanup test project สำเร็จ
- Foundation/non-integration 37 passed; Ruff lint/format (76 files), mypy (49 source files), approved OpenAPI/DTO/doc links ผ่าน
- continuity ซ้ำกับ worker ใหม่ run bef6f55a-bf72-4586-886f-c417f587eba5: start 2 events → logout 3 → ปิด Chromium process 4 → restart worker จบ reviewing 15/15 unique events/release_seq, 37/37 unique job keys
- สคริปต์ continuity exit 0 โดยไม่เร่ง clock และใช้ project soc-accept06 ฐาน/พอร์ตแยก

ติ๊กข้อ 06 และสองรายการค้างตามผล local จริงแล้ว; regression tests รวมใน CI integration script
GitHub CI ของ working changes นี้ **รอยืนยัน**; ยังไม่ commit/push/deploy
ไม่อ้างว่าข้อ 08/09 หรือข้อ 11–13 เสร็จจากผลนี้

ข้อ 07 ตรวจและเติม filters/generated DTO/cursor/backoff เพิ่มแล้ว ดู [รายงานล่าสุด](step-07-verification.md)

### เอกสารต้นฉบับ: [step-07-verification.md](step-07-verification.md)

# ข้อ 07 — Run UI / Event explorer (14 ตุลาคม 2026)

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


ทำบน codex/step-05-scenarios ที่ HEAD 2cc275f พร้อม working changes ข้อ 06 และ foundations 11–13
ไม่ switch/reset/stash หรือทับงานเดิม ไม่พบ AGENTS.md จากการตรวจ repository
ข้อ 01 มี SRS/OpenAPI/requirement mapping/scaffold/runtime pins/lockfiles อยู่แล้ว
คง training/exam boundary, finish/submit และ decision register ตาม SRS;
learning-path/RAG เป็นแบบออกแบบที่ยังไม่เปิด exam/provider/ingestion จากงาน UI นี้
ไม่มี migration/API route ใหม่ เพราะข้อ 07 ใช้ approved runs/events API ที่มีอยู่

## เปลี่ยนอะไร

- runs/page.tsx: run list/start และ cursor history พร้อมปุ่มโหลดรอบเพิ่มเติม
- runs/[runId]/page.tsx: filters q/source/asset_id/username/src_ip/from/to,
  URL state ของ filters/selected event, pause/resume และ optimistic version conflict handling
- Polling ทุก 2 วินาที, error backoff 4→8→16→30 วินาที, หยุด requests ขณะ document.hidden
- ใช้ cursor เพื่อ drain หน้า events ที่ยังมี next_cursor แล้วกลับไป after_seq โดยไม่ส่งสองค่าในคำขอเดียว
- Filter/session เปลี่ยนล้างข้อมูลเดิม; response เก่าที่ effect ยกเลิกไม่เข้า UI;
  polling ไม่ทับ run version ใหม่หลัง control; 401/403/404/422 หยุด retry อัตโนมัติ
- Request/response/log แสดงใน React text/pre ไม่ render HTML
- run-types.ts ใช้ aliases ของ generated approved API DTOs; generator ส่ง dynamic JSON เป็น Record<string, unknown>
- browser tests เพิ่ม URL filter refresh, cursor, escaped payload, loading/empty/401,
  503 backoff/recovery และ history pagination; runs.spec.ts ยังทดสอบ API/DB จริง

## ผลตรวจจริง

| Check | ผล |
|---|---|
| Local full CI script | soc-ci-ui07 exit 0; build/migrate/API/worker/UI พร้อม; cleanup เฉพาะ project ทดสอบสำเร็จ |
| PostgreSQL | 45 integration tests passed รวม runner/fencing/runs query และ investigation/auth เดิม |
| HTTP smoke | 3 passed |
| Chromium | 9 passed รวม real register/login/start S02/event/pause/refresh/resume และ widths 375/768/1440 |
| UI transport tests | Cursor/after_seq ไม่ปน, escaped script/image ไม่ execute, filters/event คงหลัง refresh, 401, empty, loading, backoff ≥3.8s ก่อน recovery, run cursor append ไม่ซ้ำ |
| Frontend | lint/typecheck/Next standalone build ผ่าน; browser assets leakage 1 test ผ่าน |
| Contract | foundation 13 passed รวม OpenAPI validation/approved drift/draft boundary; generated DTO --check ผ่าน |
| Source/static | generator Ruff ผ่าน; doc links และ git diff --check ผ่าน |

รอบแรก E2E ตรวจ Response หลังล้าง filter ซึ่งล้าง selected event ตาม UI;
แก้ test ให้เลือก event ใหม่หลัง filter reset โดยไม่ลด assertion ของ Request/Response/Log
รอบสุดท้ายทั้งหมดผ่าน ไม่มีการเรียก provider จริงหรือแตะไฟล์ key

## เปิดตรวจ

จาก root ใช้ Docker Linux engine และ secrets local ที่สร้างตามคู่มือ DB:

```powershell
$env:SOC_WEB_PORT='13006'
$env:SOC_API_PORT='18006'
$env:SOC_DB_PORT='55436'
docker compose -p soc-accept06 up --build -d --wait
```

เปิด [run list](http://127.0.0.1:13006/runs), สมัคร/login แล้วเริ่ม S02
ตัวกรอง from/to ใช้ UTC ISO 8601 ที่อยู่ในช่วง run; filter ไม่ตรงได้ empty ไม่ใช่ข้อมูลอนาคต
เปิด event แล้ว refresh เพื่อดู selected event/filter กลับมา; pause/resume ใช้ version ฝั่ง API
เพื่อทดสอบทั้งชุด ใช้ `COMPOSE_PROJECT_NAME=soc-ci-ui07 bash scripts/ci-compose.sh`
CI project เป็นฐานทิ้งได้ และลบเฉพาะ containers/volume ของชื่อนี้เมื่อจบ

## สถานะที่ยังไม่อ้าง

ข้อ 07 ผ่าน local acceptance; **รอยืนยันบน GitHub** สำหรับ working changes นี้
ยังไม่ commit/push/deploy; lockfiles/runtime pins เดิมไม่เปลี่ยน และ prototype ไม่มี diff
ข้อ 08/09 และ 11–13 ที่ยัง pending ไม่ถูกติ๊กจากผล UI นี้
rubric/retake/override-revoke unlock และ provider pipeline ตาม SRS/ไฟล์งานค้างยังแยกอยู่

### เอกสารต้นฉบับ: [step-11-verification.md](step-11-verification.md)

# ผลตรวจข้อ 11 — Evaluation, completion และ Instructor

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


ตรวจวันที่ 15 ตุลาคม 2026 บน branch `codex/step-05-scenarios` โดยเก็บงาน local เดิมไว้ทั้งหมด

การตรวจรับ local ผ่าน:

- PostgreSQL 17.11 disposable integration ผ่าน full `scripts/ci-compose.sh`: **50 passed, 30 deselected**. ครอบคลุม finish/cutoff, late analysis fencing, immutable snapshot, role grants, assignment/ownership, read-only completion, Instructor comment และ JSON export
- Chromium E2E: **11 passed** รวม flow ใหม่ login → start training → finish → evaluation snapshot → ดาวน์โหลด JSON; browser ใช้ mock provider
- Frontend HTTP smoke: **3 passed** บน Compose local stack
- Metrics/experiment tests และ OpenAPI validate/approved-contract drift: **5 passed**; A/B เรียก detector implementation จริงบน input เดียวกัน ส่วน C เป็น `unavailable`
- Generated client types `--check` ผ่าน
- Ruff, mypy, ESLint และ Next.js typecheck ผ่าน

Implementation เพิ่ม migration `0010_evaluation_and_experiments`, ตาราง snapshot ที่ DB ป้องกันการแก้ย้อนหลัง, `evaluator_runtime` แยกจาก API/worker และ evaluator service ใน Compose. `finish` ทำ cutoffs ขณะ lock run ก่อน job, evaluator drain งาน detection/analysis ไม่เกิน 60 วินาที และยกเลิก/fence output ที่มาหลัง deadline. JSON export ไม่รวม private truth.

Ground truth version ถูก pin ตอนสร้าง training run. เจ้าของอ่าน training truth ได้หลัง completion; Instructor อ่าน truth ของ run ที่ได้รับ assignment ได้ระหว่าง training และหลัง evaluation พร้อม audit. Exam routes ยังไม่เปิด. Run หลัง finish เป็น read-only; Instructor comments เป็น resource แยกและไม่มี endpoint เขียน assessment/note.

Detector metrics ใช้ detection evidence โดยไม่ให้ manual ticket หรือ soft delete เปลี่ยน denominator; zero-denominator metrics คืน `null` พร้อม reason. Human metrics คง `unavailable: HUMAN_SCORING_POLICY_UNDECIDED`; ยังไม่มี learner score จนกว่าจะอนุมัติ rubric/scoring policy. Instructor account, quota และ assignment สร้างผ่าน operator CLI; ยังไม่มี public admin user/quota API.

ข้อจำกัดที่ยังค้าง: GitHub CI ของ changeset นี้ยังไม่ได้รัน; C ยัง unavailable จนมี global provider/budget controls ที่ผ่านข้อ 12; rubric, retake และ override/revoke unlock ยัง pending. การทดสอบ local แสดง warning ที่ไม่ทำให้ fail: Starlette/httpx deprecation และ pytest cache permission ใน container.

### เอกสารต้นฉบับ: [step-12-verification.md](step-12-verification.md)

# ข้อ 12 — Free Tier provider controls

> **หมายเหตุสถานะปัจจุบัน:** การกล่าวถึง Gemini ในเอกสารนี้เป็นข้อมูลย้อนหลัง/หลักฐานของ implementation ก่อนเลือก Dify ไม่ใช่คำสั่งให้เปิดใช้หรือสถานะ provider ปัจจุบัน; repository ต้องใช้ Dify API เท่านั้น และ runtime ยังปิดจน integration ผ่านการตรวจรับ

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


วันที่ 15 ตุลาคม 2026 · branch `codex/step-12-provider-controls` จาก main หลัง PR #10 merged

## Policy ที่ผู้ใช้ยืนยัน

- Gemini 3.5 Flash-Lite, Free Tier project ไม่มี billing, synthetic training events เท่านั้น
- งบเงินจริง 0 บาท; versioned rate card `gemini-free-2026-10-15-v1` มี input/output rate 0
- global 100 dispatches/วัน UTC, 200,000 tokens/วัน, rolling 5 dispatches/60 วินาที
- quota รายผู้ใช้ 20 logical requests/วันเดิมยังบังคับ; ไม่มี fallback ไป paid model

Migration `0011_provider_budget` เพิ่ม policy และ component call reservations
แยก generation ออกจาก embedding ที่ยังไม่เปิดในข้อ 13. System policy row lock
serialize admission ระหว่าง workers; reserve ด้วย UTF-8 request bytes + framing headroom
4,096 + output cap 2,048 ก่อน network. Actual usage ใช้ provider totalTokenCount
รวมกับ input/output mapping; คืนส่วนต่างเมื่อ usage ยืนยันแล้ว.

Unknown hold ไม่หมดอายุอัตโนมัติและกัน token budget ต่อข้ามวัน. Crash หลัง admission
ไม่ dispatch เจ้าของเดิมซ้ำ. Manual retry สร้าง logical request ใหม่และต้องมี budget
ครอบคลุม unknown hold เดิม. HTTP 429 ไม่มี automatic retry, นับ dispatch ใน RPM/RPD,
คืน token hold เพราะถูกปฏิเสธและตั้ง shared cooldown 60 วินาที.
Timeout/network disconnect เป็น unknown; invalid output ที่มี usage ยังคงคิด usage.
HTTP 5xx ที่ยืนยัน usage ไม่ได้ยังกัน global hold. Provider ล่มไม่ล็อก ticket/note CRUD.

## ผล real call ที่ตรวจย้อนกลับได้

หนึ่งคำขอผ่าน runtime worker secret ใน disposable project `soc-ci-provider12test`:

| Field | ผล |
|---|---|
| arm C | `93200bc1-80d6-417e-b33d-60c3dd520d51` |
| dataset hash | `d2396ba47033098db8a1b2140ca443b231207e3974629b7bb2471ae01c46e714` |
| dispatched UTC | `2026-10-15 05:24:33.053766+00:00` |
| mode/model | real / gemini-3.5-flash-lite |
| input/output/total | 2402 / 1324 / 3726 tokens |
| reserved / settlement | 14313 tokens / consumed 3726 |
| status/error | completed / null |
| cost | 0 ตาม Free Tier/no billing ที่ผู้ใช้ยืนยัน |

A/B รัน detector จริงบน frozen S02 dataset; C คง findings/metrics ของ B
และเพิ่ม structured AI triage ที่ตรวจ citations. S02 นี้มี TP=1, TN=1, FP=0, FN=0;
นี่เป็นผลของ dataset จำลองหนึ่งชุด ไม่ใช่การรับรองคุณภาพทั่วไปหรือ human score.
Mock/injected-provider regression แยกจาก real call ด้านบน. ไม่เก็บ key, upstream bodies
หรือเนื้อหาส่วนตัวในรายงานนี้.
เก็บ metadata และ response hash ใน [หลักฐาน JSON](evidence/step-12-real-call.json).

## เปิดทดสอบและข้อจำกัด

ผลตรวจ local: full `scripts/ci-compose.sh` project `soc-ci-provider12final` exit 0;
PostgreSQL integration 55 passed, backend non-integration/contract 49 passed,
HTTP smoke 3 passed, Chromium E2E 11 passed; Ruff lint/format, mypy,
ESLint, TypeScript, Next production build และ browser asset guard ผ่าน.
New budget/C/reconciliation tests เพิ่มใน CI ผ่าน markers เดิม; ไม่เพิ่ม paid/network job.
มี Starlette/httpx deprecation warning ที่ไม่ทำให้ tests fail.

CI local รอบแรกรับ `.env` ที่เปิด real provider ทำให้ browser test คาด mock แต่ได้ real;
แก้ `ci-compose.sh` ให้ export `SOC_AI_PROVIDER=mock` เสมอ แล้วรันใหม่ผ่านทั้งชุด.
Real-call metadata ด้านบนเป็นของ explicit C smoke แยกจาก CI.

หลังตั้ง local secrets ตาม local-development.md และยืนยัน Free Tier:

```sh
COMPOSE_PROJECT_NAME=soc-ci-provider12 bash scripts/ci-compose.sh
```

API/UI เดิมยังสร้าง A/B และ C unavailable; C จริงเป็น explicit operator command
บน arm ที่ได้รับ assignment และ completed frozen run เท่านั้น:

```sh
docker compose exec worker python -m app.evaluation.real_experiment --arm ARM_UUID
```

คำสั่งนี้มี network effect และใช้ budget; ไม่เรียกใน CI. ดูผลปลอดภัยผ่าน
`tests/report_provider_acceptance.py` เฉพาะฐานทดสอบ หรืออ่าน experiment_arms/provider_calls
ผ่าน operator access. Test fixture setup อยู่ `tests/prepare_provider_acceptance.py`
และปฏิเสธ database ที่ไม่ได้ขึ้นต้น `soc_test_`.

Reconcile เฉพาะข้อมูล usage ที่ยืนยันจาก provider report โดย operator DB owner:

```sh
python -m app.analysis.reconcile --analysis ANALYSIS_UUID --tokens 123 --reason REPORT_REFERENCE
python -m app.analysis.reconcile --arm ARM_UUID --tokens 123 --reason REPORT_REFERENCE
```

ไม่อนุมาน timeout เป็น zero. คำสั่งปฏิเสธ active resource, invalid input และ settlement ซ้ำ;
บันทึก reference/time และปรับ quota ใน transaction เดียว. หาก crash แล้ว C ยัง pending
ให้คง hold ไว้และตรวจ worker ก่อน recovery; ยังไม่มี automatic reconciliation กับ Google.
Experiment C ไม่มีปุ่มเปิด real call สาธารณะ; ไม่เปิด exam/RAG/paid mode/production deployment.
GitHub CI ของ branch นี้ยังรอยืนยัน.

### เอกสารต้นฉบับ: [step-13-verification.md](step-13-verification.md)

# ข้อ 13 — Knowledge storage / offline ingestion

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


ทำบน `codex/step-13-knowledge` ใน worktree แยกจาก `origin/main` (`8c2a978`).
ผู้ใช้อนุมัติ corpus คู่มือทั่วไปสองเรื่องสำหรับ local/mock วันที่ 15 ต.ค. 2026:
อ่าน login และแยก blocked request จาก successful compromise; metadata อยู่ใน
`backend/knowledge/manifest.json`. ไม่มี private truth หรือ scenario answers ใน corpus.

## ใช้งาน

ใช้ Compose ของ worktree นี้กับ project/ports แยกจากระบบเดิม เรียก
`python scripts/init-local.py` ก่อน `docker compose up --build -d` ตาม local-development.md.
ฐานใช้ PostgreSQL 17.11 digest เดิม เพิ่ม vector 0.8.2 ผ่าน `infra/Dockerfile.pgvector`.
Image ต้นทาง extension ถูก pin digest เช่นกัน. Admin bootstrap ติดตั้ง extension
เมื่อ `SOC_INSTALL_VECTOR=yes`; migration_owner ไม่ได้ superuser หรือ CREATE DATABASE.
Managed database ต้องให้ operator ติดตั้ง extension 0.8.2 และ bootstrap schema kb
ก่อน migration wrapper; ไม่เปิด extension หรือ migrate จาก API startup.

Migration ใหม่ `0012_knowledge` ต่อจาก `0011_provider_budget`; ไม่มี dependency/lockfile
เปลี่ยน เพราะใช้ SQL casts ผ่าน asyncpg เดิม ไม่ใช้ vector ORM สร้าง schema อัตโนมัติ.

คำสั่ง operator จาก backend (ใช้ runtime env/password file ของ migration_owner):

```sh
python -m app.knowledge admit knowledge/manifest.json
# จด release UUID ที่คืนมา; Python worker จะ claim ingest_knowledge ตามปกติ
# รอ jobs succeeded แล้ว validate golden ก่อน publish
python -m app.knowledge validate RELEASE_UUID tests/knowledge_queries.json
# held-out เป็น test-only ไม่ใช้ tune threshold หรือใส่ใน index
python -m app.knowledge publish RELEASE_UUID --expected-version 1
python -m app.knowledge revoke DOCUMENT_VERSION_UUID
```

Publisher CLI ไม่มี HTTP endpoint, public upload หรือ arbitrary URL ingestion.
Worker มีสิทธิ์ insert chunks/vectors และเปลี่ยน draft เป็น ready แต่เปลี่ยน active
pointer, แก้ corpus content หรืออ่าน private truth ไม่ได้. Publisher CLI ลดสิทธิ์เป็น NOLOGIN group `knowledge_publisher` ผ่าน SET LOCAL ROLE ก่อนทำงาน;
ไม่มี DDL/private truth grant. `knowledge_ingestor` แยกสิทธิ์เขียน draft ให้ worker
โดยไม่มี publish grant. Operator credential ไม่ mount ใน worker/API.
การออก dedicated operator login แทน migration_owner session เป็น hardening ภายหลัง.

Manifest ตรวจ metadata/hash, duplicate revision, canonical path และ Markdown ที่อยู่ใต้
approved/ เท่านั้น. Admission/job IDs deterministic; version lock + lease fencing
ทำให้ transaction ที่ stale rollback ทั้ง chunks/vectors/status. Partial/revoked/empty
corpus publish ไม่ได้; publish ใช้ expected_version ของ singleton active pointer.
Content, chunks, embeddings, published release และ membership ถูก freeze ผ่าน DB guards.
Revoke ไม่ลบ snapshot แต่ filtered retrieval จะไม่คืน version นั้น รวม pinned release เก่า.

ตั้ง `SOC_KB_ENABLED=true` ใน API environment เมื่อต้องการ pin published release/config
ให้ run ใหม่ (ค่าเริ่มต้น false). API ตรวจ readiness ของ release ใน transaction start_run;
ไม่มี active หรือมี revoked member ให้ KNOWLEDGE_UNAVAILABLE และ rollback run/quota.
Run เดิมไม่ backfill และไม่เปลี่ยน release เมื่อ pointer เปลี่ยน. ขั้นนี้ยังไม่เชื่อม
triage/Ask AI/source drawer; งานนั้นอยู่ข้อ 14 และต้องตรวจ revoke ทุก response projection.

## Embedding / chunking / migration strategy

ใช้เฉพาะ fake-hash-16-v1 dimension 16, cosine exact SQL, deterministic UTF-8 byte splitter
1200 bytes/160 bytes overlap พร้อม heading/byte locator/hash. นี่เป็น byte budget
สำหรับ fake profile ไม่ได้เรียกว่า 500 model tokens และไม่ได้วัด semantic Thai quality.
Retriever จำกัด candidate 12, ผล 5, สูงสุด 2 ต่อ document version และตรวจ published/revoked.
ไม่มี confidence threshold ที่แต่งขึ้นจาก fake similarity; ใช้ทดสอบ integrity เท่านั้น.

เมื่อเลือก real embedding ต้องอนุมัติ model/dimension/tokenizer/งบก่อน: เพิ่ม immutable
profile และตาราง vector(d) ใหม่ด้วย migration, ทำ tokenizer-aware chunking/version ใหม่,
re-embed draft corpus แยก, validate golden/held-out, publish release ใหม่ แล้ว pin เฉพาะ
run ใหม่. ห้ามแก้ dimension in-place หรือผสม vector spaces. เก็บตาราง/profile เก่าจน
references หมดและ retention/rollback policy อนุญาต. ไม่มี real embedding calls ในงานนี้.

## ผลตรวจและข้อจำกัด

ผล local ที่ตรวจแล้วบันทึกด้านล่าง; fake retrieval ชุดเล็กเป็น regression ไม่ใช่
RAG quality benchmark 50 queries ตามข้อ 14. Golden และ held-out labels อยู่เฉพาะ
backend/tests/knowledge_queries.json ไม่ถูก copy ใน runner/knowledge corpus.
GitHub CI ของ branch นี้ยังรอยืนยัน; ไม่มี push/deploy/paid provider จากงานนี้.

สิ่งที่ยังไม่พร้อม: tokenizer ตาม real model, real embeddings/benchmark คุณภาพ,
retention/purge ของ immutable KB snapshots และ RAG response revocation ข้อ 14.
Golden validation ผูก membership snapshot และเป็น integrity gate ของ fake profile ไม่ใช่การอนุมัติคุณภาพโมเดลจริง.


## Local verification (15 ตุลาคม 2026)

- Ruff lint/format และ mypy ผ่าน; API contract ไม่มี route ใหม่ (operator-only lifecycle).
- Backend non-integration/contract: 53 passed; PostgreSQL integration: 58 passed
  ใน soc-ci-knowledge13 (ฐาน soc_test_foundation/tmpfs แยก).
- Test ใหม่ 4 ข้อ: UTF-8/manifest guard, ingestion/publish/revoke/ACL + golden/held-out,
  run pin/dimension/immutable/revoked admission, stale-ingestor rollback.
- Golden 2 และ held-out 2 queries ไทย/อังกฤษตรวจอันดับแรกกับ fake profile เท่านั้น.
- Full Compose/browser pipeline และผลของ GitHub ต้องดูสถานะรอบล่าสุด ไม่ใช้ผลเก่าแทน.
- Extension prerequisites และ roles ตรวจผ่านฐานจริง; ไม่มี real embedding call.


Full local Compose pipeline `soc-ci-knowledge13-full` exit 0: PostgreSQL 58,
HTTP smoke 3, Chromium 11 passed; preview-only case 1 skipped ตาม auth_only flag
ที่ไม่เปิดใน training CI. Next.js production build และ worker/evaluator readiness ผ่าน.
หลังเพิ่ม publisher group/ingestion byte cap/manifest content hash ตรวจ tests ข้อ 13 ซ้ำ.
รันซ้ำเต็มชุดด้วย `COMPOSE_PROJECT_NAME=soc-ci-knowledge13-check bash scripts/ci-compose.sh`.
CI test image รวม tests ใหม่ผ่าน markers เดิม ไม่มี network/provider call ใน tests.

Fake ingestion จำกัด 20 documents, 120KB ต่อ document และ 1MB รวมต่อ admission;
ไม่หัก logical AI quota ผู้เรียนและไม่มีเงิน/usage ภายนอก. Real embedding component
reservation/rate card ต้องทำเมื่ออนุมัติ provider/model/งบและไม่ใช้ fake budget แทน.
หากเปลี่ยน splitter ให้สร้าง document revisions/chunk set ใหม่ควบคู่ profile ใหม่;
ไม่เปลี่ยน ordinal/content ของ chunks ที่ release เก่าอ้าง.


Final targeted acceptance หลัง publisher PUBLIC-USAGE grant fix: 4 passed.
Public schema grants ทำใน admin bootstrap เท่านั้น; migration_owner มี USAGE แต่ไม่มี
สิทธิ์ grant ต่อ จึงไม่ให้ migration แอบอ้างว่า grant public schema สำเร็จ.
Ruff lint/format และ mypy ตรวจซ้ำผ่าน. ข้อ 13 ผ่าน local/mock scope;
GitHub CI ของ branch นี้รอยืนยัน. ไม่อ้าง production/real embedding readiness.

### เอกสารต้นฉบับ: [step-14-agent-review.md](step-14-agent-review.md)

# ผล agent self-review ข้อ 14

> **หมายเหตุสถานะปัจจุบัน:** การกล่าวถึง Gemini ในเอกสารนี้เป็นข้อมูลย้อนหลัง/หลักฐานของ implementation ก่อนเลือก Dify ไม่ใช่คำสั่งให้เปิดใช้หรือสถานะ provider ปัจจุบัน; repository ต้องใช้ Dify API เท่านั้น และ runtime ยังปิดจน integration ผ่านการตรวจรับ

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


ผู้ตรวจ: Codex ซึ่งเป็นผู้เขียน implementation และชุด labels เริ่มต้นด้วย ผู้ใช้อนุญาตให้ตรวจเบื้องต้น ผลนี้เป็น **agent self-review เท่านั้น ไม่ใช่ independent human review** และไม่มีการเปลี่ยนช่อง human approval หรือผล provider เดิม

ตรวจแบบ offline จาก frozen artifacts ไม่เรียก Gemini เพิ่ม ไม่ปรับ threshold ไม่แก้คำตอบย้อนหลัง ไม่ commit/push/deploy

## ขอบเขตและวิธีตัดสิน

อ่าน relevance 100 คำถาม: baseline v1 50 และ retrieval v2 50 พร้อมคู่มือ immutable 2 เรื่อง; ตรวจ sampled claims 57 รายการจากคำตอบสำเร็จ 40 รายการ ตาม sample เดิม ไม่มีการสุ่มใหม่เพื่อเลือกผลดี

- แหล่งที่เกี่ยวข้องต้องช่วยตอบสาระสำคัญของคำถามจริง ไม่ใช่เพียงมีคำเหมือนกัน คำถามทั่วไปนอก corpus ไม่มี relevant chunk
- บางคำถามตอบได้เพียงบางส่วน เช่น ชื่อ timestamp/response fields หรือขั้นตอนยืนยันกับเจ้าของบัญชี คู่มือให้หลักการแต่ไม่มีรายละเอียดครบ ระบุข้อจำกัดไว้ในเหตุผลของแต่ละ label; answerable ใน self-review หมายถึง corpus ช่วยตอบอย่างมีขอบเขต ไม่ใช่มีรายละเอียดทุกข้อ
- Claim ต้องรองรับครบทั้งข้อความด้วย event/knowledge ที่อ้างจาก context ของ operation นั้น ถ้ารองรับได้เพียงบางส่วนให้นับไม่รองรับ แม้หลักการนั้นอาจถูกต้องทั่วไป
- คำว่า denied request is not successful compromise ตีความจำกัดที่คำขอที่ถูกปฏิเสธ ไม่ใช่ยืนยันว่าทั้งระบบหรือเหตุการณ์อื่นไม่มี compromise; ประโยคประเภทนี้ควรให้คนตรวจทบทวนความกำกวมอีกครั้ง
- ตรวจ source hashes และ refs เป็น subset ของ context จริงต่อ operation แล้ว Citation ID ที่มีจริงไม่รับประกัน semantic support

## ผล

| Sample | รองรับ | อัตรา |
|---|---:|---:|
| EN no-RAG | 8/10 | 80.00% |
| EN RAG | 17/17 | 100.00% |
| กลุ่มคำถาม TH no-RAG | 10/11 | 90.91% |
| กลุ่มคำถาม TH RAG | 18/19 | 94.74% |
| รวม | 53/57 | 92.98% |

RAG รวม 35/36=97.22%; no-RAG รวม 18/21=85.71% ตัวเลขนี้เป็น self-review ของ sampled claims จากคำตอบสำเร็จเท่านั้น ไม่ใช่ success rate ของทุกคำถามหรือหลักฐานเชิงสถิติว่า RAG ดีกว่าทั่วไป 4 invalid outputs และ 1 provider failure ยังเป็น failures ใน baseline เดิม ไม่ถูกตัดให้กลายเป็น passed outcomes

Retrieval v2 จาก labels ที่ agent ตรวจ: EN Recall@5=1.00/MRR=0.975, TH Recall@5=0.95/MRR=0.95; คำถามนอกขอบเขต no-match 5/5 ต่อภาษา มี miss จริงที่ `th-authentication-03` (“การลงชื่อเข้าใช้ผ่านแล้วยังมีเรื่องใดที่สรุปไม่ได้”) ซึ่งควรเกี่ยวข้องกับ authentication แต่ไม่พบผล ไม่แก้ label เพื่อลบ miss

Corpus มีเพียงสอง chunks ทำให้ Recall@5 ชุดนี้ทดสอบ threshold/no-match มากกว่าการจัดอันดับในคลังใหญ่ ห้ามสรุปว่าได้คุณภาพเดียวกันกับ corpus กว้าง

## Claims ที่รองรับไม่ครบ

| ID | Operation | ข้อพบและเหตุผล |
|---|---|---|
| C001 | `rag14:held-v1:19:no_rag` | event แสดง denial/403 ได้ แต่ไม่มีหลักฐานรองรับคำแนะนำทั่วไปว่า checking responses/subsequent logs is necessary ซึ่งถูกใส่เป็น observation และไม่มี knowledge citation |
| C003 | `rag14:held-v1:4:no_rag` | event ไม่มี authentication event จึงไม่รองรับการอ้างว่าข้อสรุปเรื่อง authentication ถูก demonstrated by policy denial ทั้งข้อความ แม้หลักการจะสมเหตุผล |
| C029 | `rag14:held-v1:41:no_rag` | ส่วน suspicious URL เป็นหลักการเพิ่มเติมที่ไม่ได้อยู่ใน event หรือ knowledge refs; event นี้ไม่ได้ระบุว่า URL น่าสงสัย จึงรองรับไม่ครบทั้ง claim ที่เป็น observation |
| C056 | `rag14:held-v1:41:rag` | ส่วน blocked request รองรับได้ แต่การกล่าวเพิ่มเรื่อง URL อันตราย/คำขอที่เกี่ยวข้องกับ URL นั้นไม่มีใน event หรือคู่มือที่อ้าง จึงรองรับไม่ครบทั้ง observation |

ข้อพบเหล่านี้หมายถึง cited context รองรับไม่ครบ ไม่ใช่พิสูจน์ว่าทุกประโยคเป็นข้อเท็จจริงเท็จ ควรปรับ prompt/structured semantics ให้แยก observation กับ general guidance และไม่เติมเรื่อง authentication/URL ที่ไม่มีในหลักฐาน แล้วทดสอบด้วย held-out ใหม่ก่อนอ้างว่าดีขึ้น

## ภาษาและข้อจำกัด

พบ 10/30 sampled claims ในกลุ่มคำถามไทยเป็นอังกฤษล้วน (ไม่มีอักษรไทย) ซึ่งเป็นผลตรวจระดับ claim ไม่ใช่ 10 คำตอบ ทั้งคำตอบอาจผสมภาษาได้ และศัพท์เทคนิคภาษาอังกฤษไม่ได้ถูกนับเป็นปัญหาโดยอัตโนมัติ การแบ่ง TH/EN ใน benchmark คือภาษาของ query ไม่ใช่การรับรองภาษาของ output จึงยังต้องตรวจคุณภาพภาษาแยก

ไม่มี full paired answer benchmark บน release v2; grounding ด้านบนมาจาก baseline v1 จึงไม่ใช้แทน grounding ของ v2 โดยปริยาย Unknown usage 6 calls และ GitHub CI ของ changes นี้ยังค้าง ไม่มีการให้ human reviewer หรือเรียก provider เพิ่มจากงาน self-review นี้

## หลักฐานและขั้นต่อไป

- [Agent claims/relevance proposals ของ baseline](artifacts/step-14-agent-claims-review.json): 50 labels และ 57 claims พร้อมเหตุผลรายรายการ
- [Agent relevance proposals ของ v2](artifacts/step-14-agent-retrieval-review.json): 50 labels พร้อม chunk IDs และเหตุผล
- [Machine-readable summary](artifacts/step-14-agent-review-summary.json): source artifact hashes, denominators, unsupported indices และข้อจำกัด
- [คู่มือสำหรับผู้ตรวจอิสระ](step-14-review-guide.md)

ไฟล์ `*.pending.json` ของ human review เดิมยังไม่ถูกแก้ และ scorer ยังคืน pending_review เมื่อประเมิน agent proposals เพราะ independent_of_implementation=false และ approved=false ทุก label ผู้ตรวจสามารถใช้ proposals ลดเวลาการตรวจ แต่ต้องทบทวนหลักฐานและตัดสินเอง ห้ามเปลี่ยนชื่อ agent เป็นผู้ตรวจมนุษย์หรือ flip approval จากผลนี้อัตโนมัติ

เริ่มตรวจทวนที่ C001/C003/C029/C056, คำถามที่ตอบได้เพียงบางส่วน, miss ภาษาไทย และคำตอบไทยที่ใช้ภาษาอังกฤษ จากนั้นประเมิน paired answer benchmark ของ release ใหม่ด้วย labels ที่ผู้ตรวจยืนยัน ดู [ผลตรวจระบบ](step-14-verification.md) ข้อ 14 ยังไม่เสร็จและตรวจรับทั้งหมด

## รายการ sampled claims ครบ 57 ข้อ

Cxxx ใช้ลำดับ 1-based; JSON summary ใช้ indices 0-based ทุกแถวอ้าง operation และ claim_index ใน agent JSON เพื่อเปิดตรวจต้นฉบับได้

| ID | Query language/arm | Claim | Self-review | เหตุผล |
|---|---|---|---|---|
| C001 | en/no_rag | Checking responses and subsequent logs is necessary to verify policy enforcement, as demonstrated by the 403 status response and corresponding request_policy_denied event log. | รองรับไม่ครบ | event แสดง denial/403 ได้ แต่ไม่มีหลักฐานรองรับคำแนะนำทั่วไปว่า checking responses/subsequent logs is necessary ซึ่งถูกใส่เป็น observation และไม่มี knowledge citation |
| C002 | en/no_rag | The request to the restricted path was denied with a 403 status. | รองรับ | event ระบุ path /restricted และ status 403 ตรงกับ claim |
| C003 | en/no_rag | Authentication alone does not prove data access, as demonstrated by the policy denial. | รองรับไม่ครบ | event ไม่มี authentication event จึงไม่รองรับการอ้างว่าข้อสรุปเรื่อง authentication ถูก demonstrated by policy denial ทั้งข้อความ แม้หลักการจะสมเหตุผล |
| C004 | en/no_rag | A denied request is not a successful compromise. | รองรับ | ตีความเฉพาะ denied request ที่ event นี้บันทึก: การกระทำถูกปฏิเสธ ไม่ใช่หลักฐาน successful compromise; ไม่ได้ยืนยันว่าทั้งระบบปลอดภัย |
| C005 | en/no_rag | The available evidence only shows a request policy denial with a 403 status and contains no login success events. | รองรับ | frozen evidence มีเพียง denial/403 ไม่มี login success event; claim จำกัดขอบเขตที่ available evidence |
| C006 | en/no_rag | A denied request is associated with the request_policy_denied event type and status 403. | รองรับ | response.status=403 และ log.event_type=request_policy_denied ตรงกับ claim |
| C007 | en/no_rag | A request to a restricted path resulted in a 403 status and a request_policy_denied event. | รองรับ | request.path=/restricted, response.status=403, log.event_type=request_policy_denied ตรงกัน |
| C008 | en/no_rag | The provided evidence only contains a denied request event and lacks information regarding session creation or what remains unknown after it. | รองรับ | snapshot นี้มี denial event เดียว จึงไม่มีข้อมูล session creation/later activity ตามที่ claim จำกัดขอบเขต |
| C009 | en/no_rag | The provided event log shows a request policy denied response (status 403) from the web source. | รองรับ | source=web, status=403 และ event_type=request_policy_denied ตรงกัน |
| C010 | en/no_rag | A request to /restricted resulted in a policy denial with status 403. | รองรับ | path=/restricted, status=403 และ policy denial อยู่ใน event จริง |
| C011 | en/rag | A successful login records a session, but does not identify who controlled it. | รองรับ | Authentication ระบุตรงตัวว่า successful login records a session but does not identify who controlled it |
| C012 | en/rag | The request resulted in a policy denial status 403. | รองรับ | event มี policy denial และ status 403 โดยตรง |
| C013 | en/rag | A blocked request demonstrates an attempted action and an enforcement response rather than a successful compromise. | รองรับ | event ยืนยัน denial; Blocked รองรับ attempted action/enforcement และไม่สรุป compromise โดยจำกัดที่ request นี้ |
| C014 | en/rag | A denied request is not a successful compromise. | รองรับ | event แสดง denied request; Blocked รองรับว่าการปฏิเสธไม่ใช่หลักฐาน compromise ของ request นี้ ไม่ตีความเป็นทั้งระบบไม่ถูกเจาะ |
| C015 | en/rag | Inspect related events and explain which outcomes remain unknown. | รองรับ | Blocked ระบุ Inspect related events and explain which outcomes remain unknown |
| C016 | en/rag | A blocked request demonstrates an attempted action and an enforcement response, and it does not demonstrate successful compromise. | รองรับ | Blocked ระบุความพยายาม/enforcement และไม่ยืนยัน compromise; event รองรับว่ามี denial จริง |
| C017 | en/rag | Correlate the account, session, asset and time before describing impact. | รองรับ | Authentication ระบุ Correlate the account, session, asset and time before describing impact |
| C018 | en/rag | A blocked request demonstrates an attempted action and an enforcement response, but does not demonstrate successful compromise. | รองรับ | event รองรับ denial และ Blocked รองรับการแยก attempted action/enforcement จาก compromise |
| C019 | en/rag | Correlate the account, session, asset and time before describing impact. | รองรับ | Authentication ระบุ account/session/asset/time ก่อนอธิบาย impact ตรงกับ guidance |
| C020 | en/rag | A blocked request or failed authentication attempt does not demonstrate successful compromise. | รองรับ | Authentication ระบุ failed login เป็น unsuccessful attempt; Blocked ระบุ blocked request ไม่ยืนยัน compromise จึงรองรับคำแนะนำนี้ |
| C021 | en/rag | A blocked request demonstrates an attempted action and an enforcement response, not a successful compromise. | รองรับ | event รองรับ blocked action และ Blocked รองรับ attempted action/enforcement ไม่ใช่หลักฐานผลสำเร็จ |
| C022 | en/rag | Inspect related events and explain which outcomes remain unknown after a policy denial. | รองรับ | Blocked ระบุ inspect related events/unknown outcomes จึงรองรับคำแนะนำหลัง denial |
| C023 | en/rag | A successful login records a session, but does not identify who controlled it. | รองรับ | Authentication ระบุ successful login records session แต่ไม่บอกผู้ควบคุม |
| C024 | en/rag | A successful login records a session, but does not identify who controlled it, and relating sessions to later activity requires correlating the account, session, asset, and time. | รองรับ | Authentication ระบุทั้ง session ไม่บอกตัวผู้ควบคุมและการ correlate account/session/asset/time |
| C025 | en/rag | The available observation is a denied request (status 403) and does not provide session or later activity data. | รองรับ | snapshot มี denial/403 เพียง event เดียว ไม่มี session หรือลำดับกิจกรรมถัดไป |
| C026 | en/rag | Status 403 shows a request policy denial for the GET request to /restricted. | รองรับ | event ระบุ GET /restricted, status 403 และ request_policy_denied โดยตรง |
| C027 | en/rag | A blocked request demonstrates an attempted action and an enforcement response, but it does not demonstrate successful compromise. | รองรับ | Blocked ระบุ attempted action/enforcement และ does not demonstrate successful compromise โดยตรง |
| C028 | th/no_rag | คำขอถูกปฏิเสธด้วยสถานะ 403 ตามบันทึกเหตุการณ์ request_policy_denied | รองรับ | event มี status 403 และ event_type=request_policy_denied ตามข้อความ |
| C029 | th/no_rag | A denied request or the presence of a suspicious URL alone does not prove a compromise. | รองรับไม่ครบ | ส่วน suspicious URL เป็นหลักการเพิ่มเติมที่ไม่ได้อยู่ใน event หรือ knowledge refs; event นี้ไม่ได้ระบุว่า URL น่าสงสัย จึงรองรับไม่ครบทั้ง claim ที่เป็น observation |
| C030 | th/no_rag | The request to /restricted resulted in a status 403 and was denied by policy, indicating that a denied request is not a successful compromise. | รองรับ | event มี /restricted/403/policy denial; ข้อความจำกัดว่าคำขอที่ถูกปฏิเสธนี้ไม่ใช่ successful action ไม่ได้ปฏิเสธ compromise จากเหตุการณ์อื่น |
| C031 | th/no_rag | คำขอ HTTP ถูกปฏิเสธด้วยสถานะ 403 และบันทึกเหตุการณ์ระบุว่าเป็น request_policy_denied | รองรับ | event ระบุ HTTP 403 และ request_policy_denied ตรงกัน |
| C032 | th/no_rag | A denied request is not a successful compromise. | รองรับ | denied request ของ event นี้ไม่ใช่ successful action; ไม่สรุปว่าไม่มี compromise ในบริบทอื่น |
| C033 | th/no_rag | The provided evidence shows a denied request resulting in a policy denial log. | รองรับ | event แสดง denied request และ policy denial ตาม claim |
| C034 | th/no_rag | มีเหตุการณ์การปฏิเสธคำขอเข้าถึงเนื่องจากนโยบายที่เส้นทาง /restricted ได้รับการตอบกลับเป็นสถานะ 403 | รองรับ | path=/restricted, response.status=403 และ request_policy_denied ตรงกับ claim |
| C035 | th/no_rag | มีการบันทึกเหตุการณ์การปฏิเสธคำขอเข้าถึงเนื่องจากนโยบาย (request_policy_denied) | รองรับ | log.event_type=request_policy_denied อยู่จริง |
| C036 | th/no_rag | ระบบบันทึกเหตุการณ์การปฏิเสธคำขอเข้าถึงทรัพยากร (request_policy_denied) | รองรับ | event_type=request_policy_denied รองรับว่ามีบันทึกปฏิเสธคำขอ |
| C037 | th/no_rag | สถานะ 403 บ่งบอกถึงการถูกปฏิเสธนโยบายการขอเข้าถึงตามบันทึกเหตุการณ์ | รองรับ | response.status=403 และ event_type=request_policy_denied รองรับการตีความเฉพาะ event นี้ |
| C038 | th/no_rag | คำขอถูกปฏิเสธตามนโยบาย (403) | รองรับ | response.status=403 และ event_type=request_policy_denied รองรับข้อความ |
| C039 | th/rag | คำขอ HTTP ถูกปฏิเสธที่เส้นทาง /restricted โดยได้ผลลัพธ์สถานะ 403 และมีประเภทเหตุการณ์เป็น request_policy_denied | รองรับ | event ระบุ /restricted, 403 และ request_policy_denied ครบ |
| C040 | th/rag | คำขอที่ถูกปฏิเสธแสดงถึงความพยายามกระทำและมาตรการบังคับใช้ แต่ไม่ยืนยันว่าผู้โจมตีเข้าถึงระบบหรือประสบความสำเร็จในการเจาะระบบ | รองรับ | Blocked รองรับ attempted action/enforcement และไม่ยืนยัน successful compromise |
| C041 | th/rag | A denied request demonstrates an attempted action and an enforcement response, but does not demonstrate successful compromise. | รองรับ | event รองรับ denied action; Blocked รองรับขอบเขต attempts/enforcement ไม่ยืนยัน compromise |
| C042 | th/rag | Inspect related events, explain which outcomes remain unknown, and use generic guides for interpretation rather than making definitive claims about a specific incident. | รองรับ | Blocked ระบุ related events, unknown outcomes และ generic guide ใช้ interpretation ไม่ใช่ factual event claim |
| C043 | th/rag | A successful login records a session, but does not identify who controlled it. | รองรับ | Authentication ระบุ successful login records a session but does not identify who controlled it |
| C044 | th/rag | A blocked request demonstrates an attempted action and an enforcement response, and a denied request is not a successful compromise. | รองรับ | Blocked รองรับ attempts/enforcement ไม่ใช่ successful compromise; event รองรับ denied action จริง |
| C045 | th/rag | A request to /restricted returned a 403 status (request_policy_denied). | รองรับ | path=/restricted, status=403 และ event_type=request_policy_denied ตรงกัน |
| C046 | th/rag | คำขอที่ถูกปฏิเสธแสดงถึงความพยายามดำเนินการและการตอบสนองในการบังคับใช้ โดยไม่ยืนยันว่าการโจมตีสำเร็จ | รองรับ | event รองรับ denial; Blocked รองรับความพยายาม/enforcement ไม่ยืนยันความสำเร็จของโจมตี |
| C047 | th/rag | เมื่อเกิดการเข้าสู่ระบบล้มเหลว ควรตรวจสอบบัญชี session อุปกรณ์ และเวลาก่อนอธิบายผลกระทบ | รองรับ | Authentication ระบุการตรวจ account/session/asset/time ก่อนอธิบาย impact หลัง failed login |
| C048 | th/rag | เหตุการณ์คำขอที่ถูกปฏิเสธแสดงถึงการบังคับใช้นโยบาย แต่ไม่ได้ยืนยันความสำเร็จในการเข้าถึงระบบ | รองรับ | event รองรับ enforcement denial และ Blocked ระบุว่าไม่ยืนยันการเข้าถึงสำเร็จ |
| C049 | th/rag | ต้องตรวจบัญชี session อุปกรณ์ และเวลา เพื่อวิเคราะห์ผลกระทบและความสัมพันธ์ของเหตุการณ์ | รองรับ | Authentication ระบุ account/session/asset/time ก่อนอธิบาย impact และ correlation ตรงกับ guidance |
| C050 | th/rag | คำขอที่ถูกปฏิเสธแสดงถึงความพยายามและการบังคับใช้มาตรการป้องกัน แต่ไม่ยืนยันความสำเร็จของการบุกรุก | รองรับ | Blocked ระบุ attempted action/enforcement และไม่ยืนยัน successful compromise |
| C051 | th/rag | พบเหตุการณ์คำขอที่ถูกปฏิเสธ (request_policy_denied) ที่เส้นทาง /restricted ได้รับสถานะ 403 | รองรับ | event ระบุ request_policy_denied, /restricted และ 403 ครบ |
| C052 | th/rag | สถานะ 403 บันทึกเป็นเหตุการณ์ประเภท request_policy_denied สำหรับเส้นทาง /restricted | รองรับ | event ระบุ /restricted, 403 และ request_policy_denied ครบ |
| C053 | th/rag | คำขอที่ถูกปฏิเสธแสดงถึงการบังคับใช้นโยบาย แต่ไม่ยืนยันว่าผู้โจมตีเข้าถึงระบบสำเร็จ | รองรับ | Blocked ระบุ denial/enforcement ไม่ยืนยันการเข้าถึงสำเร็จ ตรงกับ guidance |
| C054 | th/rag | คำขอที่ถูกปฏิเสธแสดงถึงความพยายามกระทำและการตอบสนองเพื่อบังคับใช้นโยบาย แต่ไม่ยืนยันว่าเข้าถึงระบบสำเร็จ | รองรับ | event รองรับ blocked action; Blocked รองรับการตอบสนอง enforcement โดยไม่ยืนยัน success |
| C055 | th/rag | ควรตรวจสอบเหตุการณ์ที่เกี่ยวข้องและระบุข้อมูลหรือผลลัพธ์ที่ยังคงไม่ทราบแน่ชัดเพิ่มเติม | รองรับ | Blocked ให้ตรวจ related events และ unknown outcomes ตรงกับ guidance |
| C056 | th/rag | การพบคำขอที่ถูกปฏิเสธหรือคำขอที่เกี่ยวข้องกับ URL อันตรายแสดงถึงความพยายามและการตอบสนองด้วยการบังคับใช้นโยบาย แต่ไม่ยืนยันว่าการโจมตีประสบความสำเร็จ | รองรับไม่ครบ | ส่วน blocked request รองรับได้ แต่การกล่าวเพิ่มเรื่อง URL อันตราย/คำขอที่เกี่ยวข้องกับ URL นั้นไม่มีใน event หรือคู่มือที่อ้าง จึงรองรับไม่ครบทั้ง observation |
| C057 | th/rag | A blocked request demonstrates an attempted action and an enforcement response, and it does not demonstrate successful compromise. | รองรับ | event รองรับ blocked action และ Blocked ระบุ attempted action/enforcement ไม่ยืนยัน successful compromise |

### เอกสารต้นฉบับ: [step-14-review-guide.md](step-14-review-guide.md)

# วิธีตรวจคุณภาพข้อ 14 สำหรับผู้ตรวจ

> **หมายเหตุสถานะปัจจุบัน:** การกล่าวถึง Gemini ในเอกสารนี้เป็นข้อมูลย้อนหลัง/หลักฐานของ implementation ก่อนเลือก Dify ไม่ใช่คำสั่งให้เปิดใช้หรือสถานะ provider ปัจจุบัน; repository ต้องใช้ Dify API เท่านั้น และ runtime ยังปิดจน integration ผ่านการตรวจรับ

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


ไม่ต้องเขียนโค้ดหรือมี API key และการตรวจนี้ไม่เรียก Gemini เพิ่ม ผู้ตรวจควรเป็นคนที่ไม่ได้เขียน implementation หรือกำหนดคำตอบอ้างอิงเอง เช่น เจ้าของงาน ผู้สอน หรือเพื่อนร่วมทีม ตัวเลขจากการรันเครื่องและการตรวจความหมายของคำตอบเป็นหลักฐานคนละส่วน

## ต้องตรวจอะไร

| งาน | สิ่งที่ดู | เกณฑ์ |
|---|---|---|
| Retrieval relevance | คู่มือส่วนใดช่วยตอบคำถามได้จริง | Recall@5 ≥0.85 แยกไทย/อังกฤษ หลังคนยืนยัน relevant chunks |
| Answer grounding | ทุก claim ที่สุ่มมาตรงกับ event หรือคู่มือที่อ้างหรือไม่ | Supported claims ≥90%; รายงานแยกไทย/อังกฤษและ RAG/no-RAG |
| ข้อห้าม | คู่มือถูกใช้ยืนยันเหตุการณ์, ข้อมูลนอกหลักฐาน, หรือกล่าวว่า 403 พิสูจน์ compromise | ให้ไม่รองรับ พร้อมเหตุผล ไม่เปลี่ยน label เพื่อให้คะแนนผ่าน |

ระบบตรวจ citation UUID/FK/ownership อัตโนมัติได้ แต่ citation ที่มีอยู่จริงอาจไม่ได้รองรับข้อความนั้น เช่น event แสดง HTTP 403 และ request_policy_denied จึงรองรับว่า request ถูกปฏิเสธ แต่ไม่รองรับว่าอ่านข้อมูลสำคัญสำเร็จ ส่วนคู่มืออธิบายหลักการ ไม่ใช่หลักฐานว่าเหตุการณ์เกิดขึ้นจริง

## ชุด A: retrieval ใหม่

เปิด [retrieval review draft](artifacts/step-14-retrieval-review.pending.json) มีคำถาม 50 ข้อ (ไทย 25 / อังกฤษ 25) กับ approved chunks 2 ส่วนใน `sources` ใช้ผลจริงจาก [retrieval v2](artifacts/step-14-real-retrieval-v2.json)

อ่านคู่มือใน `sources` แล้วกรอกแต่ละรายการใน `labels`:

- `relevant_chunk_ids`: ID ของ chunk ที่เกี่ยวข้องจริง คัดจาก `sources[].chunk_id`; ถ้าไม่มีใช้ `[]` ไม่เพิ่มแหล่งอื่นนอก corpus
- `answerable`: `true` หาก approved corpus ช่วยตอบได้, `false` หากไม่มีแหล่งที่เกี่ยวข้อง ไม่ใช่ถามว่าโมเดลมีความรู้ทั่วไปหรือไม่
- `expected_evidence_ids`: หลักฐาน event ที่ต้องมีเพื่อสรุปข้อเท็จจริง คำถามคู่มือทั่วไปใช้ `[]` ได้; retrieval-only ชุดนี้ไม่ได้ยืนยันเหตุการณ์ของผู้เรียน
- `forbidden_claims`: ข้อสรุปที่ห้ามอ้างจากบริบทนี้ เช่น “พิสูจน์ว่าข้อมูลถูกขโมยแล้ว”
- `reason`: เหตุผลสั้น ๆ ว่าคู่มือรองรับเรื่องใดหรือเพราะอะไรจึงไม่มีคำตอบ
- `approved`: เปลี่ยนเป็น `true` หลังตรวจจริงเท่านั้น

กรอก `reviewer` เป็นชื่อหรือรหัสของผู้ตรวจจริง และ `independent_of_implementation=true` เมื่อผู้ตรวจไม่ได้เขียน implementation/labels เอง ช่องนี้เป็นคำรับรองของผู้ตรวจ ไม่ใช่การยืนยันตัวบุคคลจากระบบภายนอก

อย่าแก้ `artifact_sha256`, `sources`, `id`, `language`, `query` หรือรายการที่สุ่มมา ตัวตรวจปฏิเสธ context ที่ถูกเปลี่ยน/ID นอก release และรายการที่หายไป

## ชุด B: claims ของ baseline ที่รันจริง

เปิด [human review draft](artifacts/step-14-human-review.pending.json) มี 57 claims จากคำตอบ 40 รายการ (สุ่มคงที่ 10 คำตอบต่อภาษา/arm จากคำตอบที่มี claims) พร้อม `sources` และ `evidence_context` ซึ่งเป็น synthetic event ตัวเดียวกับ benchmark เดิม

แต่ละ `claims` มีข้อความ, `evidence_refs`, `knowledge_refs`, language และ arm:

1. เทียบ `evidence_refs` กับ `evidence_context` และ `knowledge_refs` กับ `sources`
2. กรอก `supported=true` เมื่อแหล่งที่อ้างรองรับข้อความทั้งหมด; ถ้าบางส่วนเกินหลักฐานให้ `false`
3. กรอก `reason` อธิบายสั้น ๆ เช่น “event ยืนยันแค่ปฏิเสธคำขอ ไม่พบหลักฐานอ่านข้อมูลสำเร็จ”
4. ถ้ายังตัดสินไม่ได้ ให้คง `null` และเขียนเหตุผล จะยังเป็น pending ไม่ถูกนับเป็นผ่าน

`labels` ในไฟล์นี้เป็นคำถาม baseline เดิมอีก 50 ข้อ ใช้ตรวจ relevance ของ baseline แยกจากชุด A; `relevant_source_ids` เป็น frozen retrieval item IDs ของ pilot เดิม ไม่ใช่ chunk UUID ของชุด A ห้ามคัด ID ข้ามชุด

ผล baseline เดิม Thai Recall@5=0.80 และมี invalid outputs/provider failure อยู่จริง แม้กรอก review ครบก็อาจได้สถานะ failed เพราะผล baseline ยังต่ำกว่าเกณฑ์ ต้องเก็บผลนั้นไว้ การประเมิน retrieval v2 ที่ดีขึ้นไม่ใช่การเปลี่ยนผล baseline ให้ผ่าน และยังไม่ใช่ full paired answer benchmark ของ release v2

## วิธีตรวจไฟล์ด้วยโปรแกรม

จาก `backend/` หลังติดตั้ง dependencies ตาม [คู่มือเริ่ม RAG](rag-development.md):

```bash
python -m app.knowledge.review assess-retrieval ../docs/artifacts/step-14-real-retrieval-v2.json ../docs/artifacts/step-14-retrieval-review.pending.json
python -m app.knowledge.review assess ../docs/artifacts/step-14-real-benchmark.json ../docs/artifacts/step-14-human-review.pending.json
```

Exit 2 = ยังตรวจไม่ครบ, exit 1 = ตรวจครบแต่ต่ำกว่าเกณฑ์, exit 0 = ผ่านเฉพาะมิติที่คำสั่งนั้นตรวจ ไม่เท่ากับครบข้อ 14/CI/deployment ผลทุกครั้งผูกกับ hash ของ artifact เดิม

หลัง review ให้แจ้งว่าตรวจไฟล์แล้ว ไม่ส่ง API key/secret ใด ๆ ขั้นถัดไปคือดูว่าจุดใดต้องแก้ แล้ววัด paired answer benchmark บน release/config ใหม่โดยใช้ held-out ที่ผู้ตรวจยืนยัน ภายใต้ global caps เดิม ไม่ใช้ผลชุดที่ปรับ threshold มาแทน held-out

## ตัวเลขล่าสุดและสิ่งที่ยังค้าง

Calibration v2 ใช้ 8 คำถามแยกจาก held-out ใหม่ทั้งหมด โดยเก็บ threshold ใน release ใหม่ ไม่เปลี่ยน pin ของ run เก่า ผล developer labels ของ retrieval v2: EN Recall@5=1.00/MRR=0.975, TH Recall@5=0.95/MRR=0.95; no-match ของคำถามนอกขอบเขต 5/5 ทั้งสองภาษา ยังต้องให้คนยืนยัน relevance ก่อนรับรองผล

ยังไม่มีคนกรอกคะแนน review, ไม่มี full paired answer benchmark ของ release v2, unknown usage เดิม 6 calls ยังไม่ reconcile และ GitHub CI ของ changes นี้ยังไม่รัน จึงยังไม่ติ๊กข้อ 14 ทั้งข้อ ดู [รายงาน](step-14-verification.md) สำหรับ checks/หลักฐานและข้อจำกัด


## Agent self-review ที่ผู้ใช้อนุญาต

ตรวจเบื้องต้นครบแล้ว ดู [รายงานและข้อพบราย claim](step-14-agent-review.md): รองรับ 53/57 claims, ไม่ครบ 4; RAG EN 17/17 และกลุ่มคำถาม TH 18/19. Relevance v2 ยังคง TH Recall@5=0.95/EN=1.00 และมี Thai miss 1 ข้อ. ผลนี้เป็นการตรวจโดย agent ที่เขียน implementation เอง ไม่ใช่ human review; original human pending files, provider artifacts และสถานะตรวจรับข้อ 14 ยังคงเดิม. ไม่มี real API calls เพิ่มจากการ review นี้

### เอกสารต้นฉบับ: [step-14-verification.md](step-14-verification.md)

# ผลตรวจข้อ 14 — RAG และ Ask AI

> **หมายเหตุสถานะปัจจุบัน:** การกล่าวถึง Gemini ในเอกสารนี้เป็นข้อมูลย้อนหลัง/หลักฐานของ implementation ก่อนเลือก Dify ไม่ใช่คำสั่งให้เปิดใช้หรือสถานะ provider ปัจจุบัน; repository ต้องใช้ Dify API เท่านั้น และ runtime ยังปิดจน integration ผ่านการตรวจรับ

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


ตรวจ local บน branch `codex/step-14-rag` ฐาน `7a5f142` (ข้อ 13); implementation ข้อ 14 ถูกรวมใน PR #13 และ GitHub Actions ผ่านสำหรับ `a4ea423` ([run 38875091514](https://github.com/IMLV1/SOC/actions/runs/38875091514)) และ `b72a549` ([run 38877535995](https://github.com/IMLV1/SOC/actions/runs/38877535995)). ตรวจซ้ำบน `main` SHA `5a1bdd4` ได้ run [38913140706](https://github.com/IMLV1/SOC/actions/runs/38913140706) ผ่านด้วย รายงานนี้ไม่ใช่หลักฐาน deploy หรือ production acceptance

## สถานะ

API/UI และ regression ที่ระบุด้านล่างผ่าน แต่ **ยังไม่ตรวจรับข้อ 14 ทั้งข้อ**: baseline เดิม Thai Recall@5=0.80 ยังคงเป็นผลไม่ผ่าน ส่วน release v2 ใช้ calibration ไทย/อังกฤษแยก แล้ววัด retrieval ใหม่ 50 ข้อได้ TH=0.95/EN=1.00 ด้วย developer labels จึงยังรอ independent relevance/grounding review, paired answer benchmark ของ release v2 และ unknown usage 6 calls ที่ต้อง reconcile จากข้อมูล provider จริง ไม่ปรับเกณฑ์หรือถือ failure เป็น success

## สิ่งที่เพิ่ม

- Authorized retrieval ด้วย pgvector แยก fake16/real768, release/config pin ต่อ run, frozen retrieval/citations และ retry snapshot เดิม ไม่รับ corpus หรือ source URL จาก client
- LangChain Core structured generation ผ่าน adapter เดิม, Pydantic/citation validation, แยก observation จาก guidance; คู่มืออย่างเดียวใช้ยืนยันเหตุการณ์ไม่ได้ ข้อมูล question/log/KB เป็น untrusted input และไม่มี tools/SQL execution
- Ticket questions API, triage RAG และ UI source drawer; loading, error, 409 draft, polling, no_match/unavailable/withdrawn และ mode ตรงจริง Source แสดง escaped text
- ตรวจ training identity ฝั่ง server; schema ปัจจุบันรับ training เท่านั้น ไม่มี exam endpoints ที่เปิด Ask AI ก่อน submit
- จอง query embedding/generation แยก component พร้อม shared rate/token/request caps; ไม่มี automatic retry ของ ambiguous provider call และ unknown usage ไม่ถูกนับเป็นศูนย์
- Revocation ตรวจ source/analysis/retry และ read projection ของ evaluation export โดยไม่เปลี่ยน immutable snapshot หรือคะแนน Instructor ใช้ assignment check เดิมร่วมกับการปิดบัง result
- Migration `0013`–`0017` เพิ่ม frozen RAG tables, dimension/profile/calibration, provider component ledger, revocation helpers และ composite FK ที่ผูก chunk/version/run/analysis; ไม่แก้ migration ที่ apply แล้ว

## ผลตรวจ local

| การตรวจ | ผล |
|---|---|
| Backend unit/contract (`pytest -m 'not integration'`) | 61 passed |
| PostgreSQL integration ทั้งชุด | 65 passed |
| PostgreSQL RAG/provider-budget หลังเพิ่ม reservation bounds, lease fencing และ HTTP revocation/replay checks | 11 passed ก่อนเพิ่ม review-only tests; full integration ล่าสุด 65 ผ่าน |
| Ruff check/format และ strict mypy จาก backend directory | ผ่าน |
| Approved OpenAPI validation, FastAPI contract drift และ generated TypeScript client | ผ่าน |
| Full disposable Compose CI | exit 0: PostgreSQL 65, HTTP smoke 3, Chromium 12 passed; preview-only 1 skipped ตาม environment |
| Frontend หลังปรับ source drawer ป้องกัน stale response | lint/build, asset guard และ targeted Assistant Playwright ผ่าน |
| Local Markdown links / git whitespace | ผ่าน |

Full Compose รอบล่าสุดใช้ project ทิ้งได้ `soc-ci-rag14-final` และ mock provider เท่านั้น; ตัว review tool/เอกสารที่เพิ่มภายหลังตรวจด้วย unit/static checks แยก ไม่ใช้การรัน provider จริงใน CI

Regression ครอบคลุม cross-run/event/knowledge citations, observation ที่ไม่มี event, prompt injection, no-match ไม่เรียก generation, retry frozen context, withdrawal/source 410/export และ immutable metrics, ownership/CAS/idempotency, finish/question race, non-training deny, unknown reconciliation, global budget เต็มไม่หยุด detector/tickets และ fake/real vector-space isolation

## Real Free Tier acceptance

ตัวเลขในส่วน baseline ด้านล่างเป็น checkpoint ก่อน calibration v2; ตัวเลขล่าสุดรวมทุกการเรียกอยู่ในส่วนการแก้เพิ่มและ ledger artifact ท้ายรายงาน

ได้รับอนุมัติ Gemini Free Tier ไม่มี billing, `gemini-embedding-2` 768 dimensions และ `gemini-3.5-flash-lite` เฉพาะข้อมูลจำลอง/คู่มือทั่วไป 2 เรื่องที่อนุมัติ งบเงินจริง 0 บาท; caps 100 dispatches/วัน UTC, 200,000 tokens/วัน และ 5 dispatches/60 วินาที ไม่มีการเปิด paid mode หรือ provider บน Render

[Benchmark artifact](artifacts/step-14-real-benchmark.json) เก็บคำถาม/ผล/สถานะ/model/call IDs และ configuration; [API smoke artifact](artifacts/step-14-real-api-smoke.json) เก็บ analysis/source และ export hash โดยไม่เก็บ session/key หรือ raw private evaluation

- Pilot 50 held-out questions: อังกฤษ 25, ไทย 25; RAG/no-RAG รวม 100 arm outcomes
- 95 outcomes succeeded (รวม 14 no-match templates ที่ไม่ dispatch generation), invalid output 4 และ provider failure 1 เก็บ `result=null` ตามจริง ไม่ retry แบบกลบ failure
- English RAG Recall@5 1.00, MRR 0.975; Thai Recall@5 0.80, MRR 0.775
- p50 generation/template latency ไม่รวม retrieval/embedding: EN no-RAG 2344 ms / RAG 2312 ms; TH no-RAG 7797 ms / RAG 4609 ms ไม่ใช้ตัวเลขนี้อ้าง end-to-end latency
- รวมการเตรียม corpus/calibration/smoke/benchmark/API acceptance: 98 tracked dispatches (document embedding 2, query embedding 5, generation 91), known usage 87,187 tokens และ unknown holds 47,207 tokens จาก 6 calls รวม 134,394 ภายในเพดาน 200,000 ไม่มีการ reset ledger เพื่อข้าม caps
- ค่าใช้จ่ายจริงที่ยืนยันครบยังเป็น `null` เพราะ unknown usage ไม่สรุปว่า provider รายงาน 0 บาทแม้เลือก project Free Tier/no billing
- Historical embedding calls 5 ครั้งยัง unknown เพราะ mapping เดิมไม่เก็บ `promptTokenCount`; mapping ใหม่ตรวจ real embedding ได้ 768 dimensions/3 tokens แต่ไม่ใช้ค่านั้นย้อนประมาณ usage เก่า อีก 1 call เป็น provider failure
- Current API smoke ใช้ FastAPI TestClient + session/CSRF + PostgreSQL + real worker/provider: question → matched structured answer → source → finish → frozen evaluation/export ผ่าน นี่ไม่ใช่การเดิน browser กับ Gemini end-to-end; browser tests ใช้ controlled API และ Compose integration แยกกัน

Benchmark ใช้ Question-v1 schema เดียวกันทั้งสอง arms ตลอดการ resume ไม่สลับ schema ตาม production metadata ที่เพิ่มภายหลัง; invalid output คงเป็น failure Label ของ pilot เป็น developer-authored ยังไม่ใช่ independent human review ไม่ปรับ threshold จาก held-out นี้แล้วนำผลเดิมมาอ้างใหม่

## วิธีเริ่มและงานค้าง

ดู [คู่มือ RAG](rag-development.md) สำหรับ mock local, operator ingestion/calibration/publish, flags และ reconciliation CLI ค่าเริ่มต้นปิด real calls และ CI ใช้ fake embeddings ไม่ index `docs/` ทั้งโฟลเดอร์

## การแก้เพิ่มตาม docs วันที่ 16 ต.ค. 2026

- Model tokenizer: preflight `countTokens` พร้อม system/schema ก่อน generation จริง; fail closed หากใช้ tokenizer ไม่ได้/เกิน 16k รวม output เผื่อ 1200 และตรวจ lease/revocation อีกครั้งก่อน chat ขนาด evidence/KB ยังคง byte cap ที่เข้มกว่า token cap เป็นด่านแรก
- แต่ละ count HTTP request อยู่ใน shared 100/day/5-per-minute cap, เก็บ counted input แยกจาก usage ที่ generation ใช้; ไม่มีการเอา counted tokens ไปคิดซ้ำ ตัว request admission เผื่อ embedding + count + chat 3 dispatches
- Numeric provider telemetry แยก input/output/thinking/latency และ retrieval SQL latency; ไม่บันทึก prompt/key/raw provider error
- Bilingual validation 8 queries แยกจาก held-out v1/v2 ทั้งหมด สร้าง release ใหม่ `a2808f51-f9fa-5fbe-8e91-441a4345980a` พร้อม threshold 0.4321524661316025 ไม่แก้ policy/run pins เก่า ดู [calibration](artifacts/step-14-real-calibration-v2.json)
- [Retrieval v2](artifacts/step-14-real-retrieval-v2.json): 50 คำถามใหม่, 20 answerable/5 unanswerable ต่อภาษา; EN Recall@5=1.00/MRR=0.975, TH Recall@5=0.95/MRR=0.95; unanswerable no-match 5/5 ทั้งสองภาษา ผลนี้ยังเป็น developer relevance labels ไม่ใช่ human-approved acceptance และไม่แทน baseline answer comparison
- [Real tokenizer smoke](artifacts/step-14-real-tokenizer-smoke.json): count 841 input tokens แล้ว generation succeeded; provider usage 1113 tokens; 2 dispatches นี่เป็น adapter smoke ไม่ใช่ browser/API acceptance รอบใหม่
- [Ledger/latency](artifacts/step-14-ledger-and-latency.json): รวม 109 dispatches ข้าม 2 วัน UTC (15 ต.ค. 95 /16 ต.ค. 14); known tokens รวม 89,213, unknown holds 47,207 จาก 6 calls ทุกวันยังต่ำกว่า caps เดิม; ไม่ reset ledger หรือส่ง ambiguous call ซ้ำ
- Retrieval SQL 25 samples/ภาษา: p50 rounded 0ms/p95 16ms (ความละเอียดเป็น ms), embedding batch 1985ms ร่วม 50 คำถาม ไม่ใช่ per-query end-to-end latency; tokenizer/generation smoke มีอย่างละ 1 sample ไม่อ้างว่าเป็น p95 ของระบบ
- เตรียม [คู่มือผู้ตรวจ](step-14-review-guide.md), review packets ที่ยังไม่มีคะแนนมนุษย์ และ offline scorer ซึ่งปฏิเสธ stale artifact, context/claim ที่แก้, cross-release refs, missing samples และไม่ตัด unsupported claims ออกจาก denominator

ต้องทำต่อก่อนตรวจรับคุณภาพ:

1. ผู้ตรวจอิสระยืนยัน relevant chunks ของชุด v2 และตรวจ supported claims ≥90% จาก evidence/context ที่แนบ ดูคู่มือ review; ไม่ให้ agent ที่เขียนงานลงคะแนนแทนมนุษย์
2. วัด full paired answer comparison บน release/config v2 หลังได้ labels ที่ผู้ตรวจยืนยัน; เก็บ baseline v1 ที่มี 4 invalid outputs/1 provider failure ไว้ ไม่ใช้ retrieval-only เป็นหลักฐานคุณภาพคำตอบ
3. Reconcile unknown usage ด้วยรายงาน provider ที่ยืนยันได้และ audit; เก็บ ledger ใน local container `soc-ci-rag14-real-db` ไม่ลบเพื่อเริ่มนับงบใหม่
4. GitHub CI ผ่านแล้วตาม run IDs ข้างต้น; การตรวจรับเชิงคุณภาพและ unknown usage ยัง pending จึงยังไม่ปิดข้อ 14

## ตรวจเพิ่ม 17 ต.ค. 2026

- ผู้ใช้กำหนดให้เลื่อน real-AI quality acceptance และ reconciliation ไปทำภายหลัง; ไม่มีการเรียก provider เพิ่ม และการเชื่อมต่อจริงยังคง opt-in ตาม config
- เปิด Google AI Studio Usage แบบ read-only ในบัญชีที่เปิดอยู่ เลือก `Default Gemini Project` ช่วง 28 วันแล้ว dashboard แสดง `No data available`; นี่ไม่ยืนยันว่า 6 unknown calls ใช้ 0 tokens เพราะยังจับคู่ project/call IDs ไม่ได้
- ลิงก์ metrics ไป Google Cloud Console แต่หน้า Console ขอให้ยอมรับ Terms of Service ก่อนดู metrics จึงหยุดไว้ที่หน้านั้น ไม่ยอมรับข้อตกลงแทนผู้ใช้ และยังไม่มี provider report สำหรับ reconcile
- รัน offline assessors กับ pending packets: `assess-retrieval` และ `assess` คืน `pending_review` (exit 2; reviewed sample count 0) ตามคาด เพราะยังไม่มีผู้ตรวจกรอกผล

ตรวจเอกสารจาก repository root ด้วย `python3 scripts/check-doc-links.py` และ `git diff --check`; backend checks รันจาก `backend/` ตาม AGENTS เพื่อให้ strict config มีผล

## ตรวจตามคำสั่งผู้ใช้ 18 ต.ค. 2026

- ผู้ใช้สั่งให้เดินหน้าปิด independent quality review และ reconcile unknown usage; real provider dispatch ยังปิดไว้ ไม่มีการส่งคำถามหรือข้อมูลเพิ่มไป Gemini.
- ตรวจหน้า Google Cloud Console Metrics ในบัญชีที่เปิดอยู่แบบ read-only; หน้าแรกขอให้ยอมรับ Google Cloud Platform/บริการ Terms of Service ก่อนดำเนินต่อ และ checkbox ยังไม่ถูกเลือก. ไม่ยอมรับข้อตกลงแทนผู้ใช้. จึงยังไม่มี usage report ที่จับคู่กับ 6 internal call IDs ได้.
- Human review packets ยังคง pending. ผู้ช่วยเป็น agent ที่จัดทำ implementation และ prior self-review; กรอก reviewer/labels แทนคนอิสระจะทำให้หลักฐานคลาดเคลื่อน จึงคงผล 53/57 agent-supported claims เป็น self-review เท่านั้น.
- ขั้นต่อไปที่จำเป็น: ผู้ใช้หรือผู้ตรวจอิสระกรอก review packet; สำหรับ usage ต้องให้เจ้าของบัญชียอมรับ Terms of Service และตรวจ project/ช่วงเวลาให้ตรงกับวันที่เรียกก่อนดาวน์โหลด usage details. หาก report ไม่มี call-level mapping จะคง 6 calls เป็น unknown hold ต่อ ไม่เปลี่ยนเป็น 0.


## Agent self-review ที่ผู้ใช้อนุญาต

ตรวจเบื้องต้นครบแล้ว ดู [รายงานและข้อพบราย claim](step-14-agent-review.md): รองรับ 53/57 claims, ไม่ครบ 4; RAG EN 17/17 และกลุ่มคำถาม TH 18/19. Relevance v2 ยังคง TH Recall@5=0.95/EN=1.00 และมี Thai miss 1 ข้อ. ผลนี้เป็นการตรวจโดย agent ที่เขียน implementation เอง ไม่ใช่ human review; original human pending files, provider artifacts และสถานะตรวจรับข้อ 14 ยังคงเดิม. ไม่มี real API calls เพิ่มจากการ review นี้

## ตรวจหลักฐาน read-only ซ้ำ 20 ต.ค. 2026

- เปิด Google AI Studio Usage ในบัญชีที่ลงชื่ออยู่โดยไม่เปลี่ยน project/config: `Default Gemini Project`, Free tier, ช่วง 28 วัน หน้าสรุปคำขอ, error, token และ embedding แสดง `No data available` ทั้งหมด แม้ช่วงนี้ครอบคลุมวันที่ dispatch ใน ledger; ไม่ถือว่าเป็นหลักฐานว่า 6 calls ใช้ 0 tokens หรือไม่มีค่าใช้จ่าย. หน้า dashboard แจ้งว่าข้อมูลอาจหน่วงได้ถึงประมาณ 15 นาที; เอกสาร Google ระบุจุดตรวจ usage ที่ Dashboard > Usage ([เอกสาร billing/usage](https://ai.google.dev/gemini-api/docs/billing)).
- เปิดหน้า Logs and Datasets แบบอ่านอย่างเดียว พบสถานะ `Disabled`; ไม่เปิด logging หรือเปลี่ยน telemetry settings. เอกสาร Google ระบุว่าการเก็บ Gemini API logs ใช้ได้เฉพาะ project ใน paid tier จึงไม่เปิด paid tier เพื่อไล่หาหลักฐาน usage ([เอกสาร Logs and Datasets](https://ai.google.dev/gemini-api/docs/logs-datasets)).
- Google Cloud Console Metrics ยังแสดง Terms of Service ที่ยังไม่ยอมรับ; ไม่เลือก checkbox หรือกดยอมรับแทนเจ้าของบัญชี จึงไม่มี Cloud Monitoring report เพิ่ม.
- รัน offline assessors ซ้ำจาก `backend/`: retrieval v2 และ paired relevance/grounding คืน `pending_review`, `sample_count=0`; agent self-review 53/57 claims ยังไม่ใช่ independent human acceptance.
- ไม่ได้ dispatch provider calls เพิ่ม. สถานะ 6 calls คงเป็น `unknown`; usage dashboard ที่ไม่มีข้อมูลและ logging ที่ปิดอยู่ไม่สามารถจับคู่ provider usage กับ internal call IDs ได้. ยังขาดผู้ตรวจอิสระเพื่อยืนยัน labels และหลังจากนั้นจึงทำ paired answer benchmark ของ release v2 ได้โดยไม่ปนผล developer labels.

### เอกสารต้นฉบับ: [step-15-verification.md](step-15-verification.md)

# Step 15 verification — learning path and server-side progress

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


## Implemented

- One versioned, training-only beginner lesson with five ordered steps: Method/Path, Response, account/IP, timeline, and evidence limits.
- FastAPI routes for metadata, authenticated lesson content, owner-scoped progress, ordered step completion, and lesson completion. Mutations require JSON, Origin, CSRF, rate limiting, and `expected_version`; clients cannot supply owner, passed, or unlocked state.
- PostgreSQL migration `0019_learning_path` and one-shot operator seeder (`cd backend && python -m app.learning.seed`). The seeder refuses to alter an already published lesson version.
- Next.js `/learning` UI resumes from server progress after refresh and clearly says lesson completion is not exam pass. Guest sees metadata and a login prompt.
- User decision (2026-10-17): login is required to read lesson content, overriding the older Guest review sentence in `learning-path.md`.

## Verification status

Local rerun on 2026-10-18 after Docker Engine became available:

- Full disposable Compose run on 18 Oct: migrations and health checks passed; PostgreSQL integration suite 80 passed / 81 deselected; HTTP smoke 3 passed; worker/evaluator readiness passed; browser E2E 22 passed and 1 skipped.
- `test_learning_progress_persists_across_refresh_and_is_owner_scoped` verifies guest content denial, metadata access, server persistence across fresh clients, stale-version conflict, owner isolation, and rejection of exam start before lesson completion.
- Browser E2E registers and logs in, completes lesson steps, verifies persistence after refresh, checks 375/768/1440 px layouts, starts an exam only after completion, submits an answer, and confirms the result remains `needs_review` rather than auto-passing.
- Targeted Ruff check/format passed for the added integration test; frontend lint/typecheck and `git diff --check` passed.

Earlier local checks passed on 2026-10-17:

- Pinned Python 3.12.14 backend environment: Ruff check/format, mypy, 80 non-integration tests, OpenAPI validation, and generated-client drift check.
- Pinned Node 24.20/npm 11.19 frontend environment: `npm ci`, lint, typecheck, production build, and built-assets leakage test.
- Python compile check, OpenAPI YAML parse, Markdown links, and `git diff --check`.

Local acceptance for step 15 is now covered by the PostgreSQL and browser tests above. `docs/openapi.yaml` remains draft pending feature review, and no GitHub CI or deployment result is claimed.

## Remaining product verification

1. Continue step 16 with concurrent-submit and retake behavior tests; the learner exam browser flow now passes.
2. Run GitHub CI on the final commit before release; no new CI result is claimed here.
3. Run a manual keyboard/accessibility review of `/learning`; responsive overflow is covered by browser tests, not a full accessibility audit.

### เอกสารต้นฉบับ: [step-16-verification.md](step-16-verification.md)

# ผลตรวจข้อ 16 — blind exam และ immutable submission

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


ตรวจ working tree บน branch `implementation-checklist` วันที่ 20 ตุลาคม 2026. ข้อนี้ยัง **ไม่ผ่านตรวจรับ**; checklist จึงยังไม่ติ๊ก

## สิ่งที่เพิ่ม

- Migration `0019_learning_path` และ `0020_exam_attempts` เพิ่ม lesson/progress, run mode, exam bank, private truth, attempt, frozen answer, grading revision และ level unlock; migration graph ตรวจพบ head `0020_exam_attempts` ต่อจาก `0019_learning_path`.
- Operator seed รวม training scenario, lesson และ exam bank ให้ Compose เรียกหลัง migration; exam truth อยู่ใน privileged seed image เท่านั้น. Runner ได้เฉพาะ sanitized event fixtures; API/frontend ไม่บรรจุ fixture assets.
- Exam fixtures สามกรณีใช้ชื่อ public แบบเดียวกันและไม่ใส่ label/expected result ใน learner projection.
- API เลือก case ฝั่ง server, ตรวจ lesson completion/version, active attempt, quota/cooldown, idempotency และ evidence ที่อยู่ใน released events ของ run เดียวกัน; submit freeze answer/cutoff และปิด run ใน transaction เดียว.
- Learner UI แสดงข้อสอบ, evidence, answer form, pending review และกู้ active attempt หลัง refresh ผ่าน API; ไม่มี authoritative data ใน browser storage.
- Learner UI กู้ผล finalized ล่าสุดหลัง refresh และเปิดทางเริ่ม attempt ใหม่เมื่อผลเป็น `failed|expired`; API latest-result จำกัดข้อมูลตามเจ้าของและไม่ส่งเฉลย.

## ผลตรวจ local

ผลตรวจล่าสุด 21 ต.ค. 2026: disposable Compose ผ่าน migration/seed/health checks; integration suite **81 passed / 81 deselected**, smoke **3 passed**, browser E2E **26 passed / 1 skipped**. Integration ยืนยัน start/idempotency, blind projection, submit/replay, owner isolation, lesson gate, concurrent Instructor review, unlock เมื่อผ่านครบทุก case, revision/audit, override ที่ไม่ถอน unlock, case cap และการแข่งเริ่ม retake หลัง attempt ก่อนหน้าตกและ cooldown หมด (มี active attempt ได้เพียงหนึ่งเดียว). Browser E2E ครอบคลุมเริ่มข้อสอบ ส่งคำตอบ `needs_review`, Instructor review จริงใน disposable DB, learner feedback หลัง refresh และการปฏิเสธ retry ระหว่าง cooldown. Retake policy กำหนด 3 attempts/case/24h (สูงสุด 9/level), case rotation/cap และ cooldown 1h หลัง fail. API ล่าสุด-result จำกัด ownership ผ่าน integration.

- Ruff lint/format ของไฟล์ backend ที่แก้, mypy และ `pytest -m 'not integration'`: ผ่าน; **93 passed** (deselected count แปรตาม integration tests ที่เพิ่ม; ล่าสุด 80).
- เพิ่ม `test_exam_integration.py` ครอบคลุม start/idempotency, frozen submit/replay, owner isolation และ assignment-scoped review; Compose integration suite ผ่านจริงบน PostgreSQL.
- OpenAPI YAML validation และ generated client check: ผ่าน. Exam routes ยังซ่อนจาก OpenAPI เพราะ contract เป็น draft.
- Frontend typecheck/lint/build ผ่าน; browser asset leakage test และ production landing smoke ผ่านอย่างละ 1 test.
- `git diff --check` ผ่าน.

## ยังต้องยืนยัน

Browser E2E ที่เพิ่มภายหลังเดินจากผล failed ผ่าน cooldown ไปเริ่ม attempt ใหม่ได้จริงบน disposable Compose; ดูหัวข้อ “ตรวจ browser retake หลัง cooldown” ในรายงานข้อ 16 ด้านบน. Compose integration และ browser flow ไม่ใช่ staging/deployment acceptance; เรียก Alembic ผ่าน migration wrapper ตาม harness.

## เพิ่มเติม 20 ต.ค. 2026

เพิ่ม `frontend/tests/browser/exam-review.spec.ts` สำหรับ UI contract ด้วย fixture และต่อยอด `frontend/tests/browser/learning.spec.ts` ให้ใน disposable Compose ทำ browser journey จริง: Analyst สมัคร/เรียน/ส่งข้อสอบ → operator provisions Instructor ชั่วคราวและ assign เฉพาะ Analyst → Instructor login/ตรวจคำตอบผ่าน UI/API → Analyst refresh แล้วเห็นผลและ feedback จาก PostgreSQL. รหัสผ่านสุ่มเฉพาะ run อยู่ในไฟล์ชั่วคราวและฐาน/volume ถูกลบโดย harness. วันที่ 20 ต.ค. 2026 `scripts/ci-compose.sh` ผ่าน: backend/PostgreSQL integration **81 passed**, smoke **3 passed**, browser **23 passed / 1 skipped**. GitHub CI ทุก job ผ่านบน commit `75ae111870c1c4da1ae152b0d16519ad723d5901` (run [39411788826](https://github.com/IMLV1/SOC/actions/runs/39411788826)). รอบก่อนหน้าล้มเพราะ container ใช้ UID `soc` ซึ่งอ่านไฟล์รหัสผ่านชั่วคราวที่สร้างเป็น mode `0600` โดย CI runner ไม่ได้; `scripts/ci-compose.sh` กำหนด UID/GID ให้ตรงเจ้าของไฟล์ก่อน provision. Docker CLI บนเครื่องนี้เรียกผ่าน `PATH="$PATH:/Applications/Docker.app/Contents/Resources/bin"`.

## ตรวจซ้ำ 21 ต.ค. 2026

บน checkout ก่อนหน้า (branch `codex/magic-ui-redesign`) `scripts/ci-compose.sh` ผ่าน migration/health, PostgreSQL integration **81 passed**, HTTP smoke **3 passed**, worker/evaluator readiness และ browser E2E **26 passed / 1 skipped**. ผล branch ปัจจุบันและ browser retake หลัง cooldown อยู่ในหัวข้อ “ตรวจ browser retake หลัง cooldown” ของรายงานข้อ 16.

### เอกสารต้นฉบับ: [step-17-verification.md](step-17-verification.md)

# ผลตรวจข้อ 17 — grading, feedback, review และ unlock

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


ตรวจ working tree บน branch `implementation-checklist` วันที่ 18 ตุลาคม 2026. ข้อนี้ยัง **ไม่ผ่านตรวจรับ**; checklist จึงยังไม่ติ๊ก

อัปเดต local evidence 18 ต.ค. 2026: Compose migration/health checks ผ่าน; integration **80 passed / 81 deselected**, smoke **3 passed**, browser E2E **22 passed / 1 skipped**; worker/evaluator readiness ผ่าน. Integration ยืนยัน concurrent review ให้ผู้ชนะหนึ่งคำขอ, ปลดล็อกหลังผ่านครบสาม case, append override revision/audit และไม่ถอน unlock เดิม. Browser E2E ยังไม่มี flow feedback/Instructor review.

## Policy และ implementation

ค่าเริ่มต้น D-01–D-04 ที่ผู้ใช้มอบหมายอยู่ใน [SRS §8](srs.md#8-decision-register--ข้อสรุปที่ผู้ใช้มอบหมายให้กำหนด-และเรื่องที่ยังค้าง): rubric `soc-foundations-v1` 4 criteria, 0–2 คะแนนต่อเกณฑ์, ผ่านเมื่อได้อย่างน้อย 6/8 และ critical criteria `evidence`/`analysis` ต้องได้อย่างน้อย 1. Evidence ต้องอ้าง released events ใน run เดียวกัน. Missing/invalid/ambiguous input ต้องไม่ auto-pass. จำกัด 3 attempts ต่อ level ต่อ rolling 24 ชั่วโมง, cooldown 1 ชั่วโมงหลัง fail, attempt หมดอายุ 24 ชั่วโมง; override append revision/audit แต่ไม่ถอน unlock ที่ได้แล้ว.

เพิ่ม deterministic rubric, frozen answer, grading revisions, assignment-scoped Instructor truth access หลัง submit, audit ของการอ่าน truth, human review, feedback projection และ level unlock ที่สร้างครั้งเดียว. เพิ่มคิว Instructor และหน้าอ่านคำตอบ/เฉลย/ให้คะแนน. **Real AI/provider grading ยังไม่เปิด** ตามขอบเขตที่ผู้ใช้กำหนด; ไม่มีค่าใช้จ่าย/provider call.

## ผลตรวจ local

- Ruff lint/format ของไฟล์ backend ที่แก้, mypy และ `pytest -m 'not integration'`: ผ่าน; **93 passed** (deselected count แปรตาม integration tests ที่เพิ่ม; ล่าสุด 80).
- เพิ่ม integration coverage สำหรับ assignment-scoped truth/review; Compose integration suite ผ่านจริงบน PostgreSQL.
- Frontend typecheck/lint/build ผ่าน; browser asset leakage test และ production landing smoke ผ่านอย่างละ 1 test.
- Migration graph ชี้ `0020_exam_attempts` เป็น head; `git diff --check` ผ่าน.

## ยังต้องยืนยัน

ณ รายงานเดิมยังขาด browser E2E ของ learner feedback กับ Instructor review; มีหลักฐานเพิ่มในวันที่ 20 ต.ค. 2026 ด้านล่าง. Integration race/override/unlock coverage ฝั่ง PostgreSQL ยังไม่ครอบคลุมทุก interleaving. AI grading จริงและ citations ยังไม่เปิดตาม scope ที่ผู้ใช้ระบุ.

## เพิ่มเติม 20 ต.ค. 2026

เพิ่ม browser UI regression ใน `frontend/tests/browser/exam-review.spec.ts` และ full-stack browser journey ใน `frontend/tests/browser/learning.spec.ts`: Instructor จริงใน disposable DB ตรวจคำตอบของ Analyst ที่ assigned ผ่านหน้าเว็บ/API และ Analyst เห็นผล/feedback หลัง refresh. วันที่ 20 ต.ค. 2026 local disposable Compose ผ่าน integration 81 tests, smoke 3 tests, browser 23 passed/1 skipped; PostgreSQL integration ครอบคลุม assignment, concurrent review, unlock และ override. GitHub CI ทุก job ผ่านบน commit `75ae111870c1c4da1ae152b0d16519ad723d5901` (run [39411788826](https://github.com/IMLV1/SOC/actions/runs/39411788826)). ยังขาด coverage interleavings เพิ่มเติม; Step 17 ยังขึ้นกับการตรวจรับ Step 14 ตามลำดับ checklist จึงยังไม่ติ๊ก.

### เอกสารต้นฉบับ: [step-18-verification.md](step-18-verification.md)

# ผลตรวจข้อ 18 — staging deployment และ operations

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


ตรวจ source tree บน branch `implementation-checklist` ณ 17 ตุลาคม 2026

อัปเดต 18 ต.ค. 2026: Docker Desktop 4.95.0 / Engine 29.8.2 ติดตั้งและทำงานได้; local Compose build, migration, integration **79 passed / 80 deselected**, smoke **3 passed**, E2E **22 passed / 1 skipped**, worker/evaluator readiness checks ผ่าน. นี่เป็น local validation เท่านั้น.

## สิ่งที่มีใน checkout

- `backend/Dockerfile` มี pinned Python base image และ target `api`, `runner`, `seed`, `test`; target เริ่มต้นเป็น API และ fixture แยกจาก API image
- `frontend/Dockerfile` มี pinned Node base image และ standalone Next.js build
- `.github/workflows/ci.yml` ทดสอบ prototype, backend, frontend และ integration; ไม่มี image publish/deploy job
- `scripts/ci-compose.sh` ใช้เฉพาะ `soc-ci-*` isolated Compose project และทำ integration/E2E cleanup; ไม่ใช่ staging deploy/rollback script
- API มี `/health/live` และ `/health/ready`; worker/evaluator มี `--check` command ใน CI harness
- `docs/ci-cd.md` ระบุชัดว่า provider, registry, domain และ environment credentials ยังไม่ถูกเลือก/ตั้งค่า

## ยังไม่ได้ทำหรือยืนยัน

ยังไม่มี staging environment/registry/hosting credentials ที่ยืนยันได้ จึงไม่มี immutable release image digest, deploy/migrate/rollback run, HTTPS acceptance หรือ backup/restore evidence ให้รายงาน

ไม่สร้าง deployment adapter หรือ workflow ที่เดา provider/credentials และไม่ publish/deploy ภายนอก การสร้างไฟล์ deploy ที่ยังไม่ผูกกับ environment จะไม่พิสูจน์ staging acceptance ตาม checklist

## ขั้นตอนที่ต้องทำเมื่อ environment พร้อม

1. เลือก hosting/registry/domain และแยก staging DB/credentials ตามบทบาทใน [ci-cd.md](ci-cd.md).
2. รัน GitHub CI บน SHA ที่จะปล่อย แล้ว build API/worker/web images; เก็บ immutable digests ใน release manifest.
3. รัน migration แบบ one-shot ด้วย migration role, deploy API/worker/web และตรวจ readiness/heartbeat/queue/pgvector.
4. ทำ authenticated smoke flows, HTTPS/cookie/CSRF checks, application rollback drill และ backup restore ไป DB ใหม่; เก็บผลและ SHA/digests.

ข้อ 18 ยังไม่ผ่านและ checklist ยังคง unchecked. ไม่มี external action ในรอบนี้.

### เอกสารต้นฉบับ: [step-19-verification.md](step-19-verification.md)

# ผลตรวจข้อ 19 — requirement coverage และ acceptance gaps

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


ตรวจ source/docs ใน branch `implementation-checklist` วันที่ 17 ตุลาคม 2026 เป็น coverage audit ไม่ใช่ final acceptance, production release หรือ deployment report; มีการตรวจซ้ำบน `codex/magic-ui-redesign` วันที่ 21 ต.ค. 2026 ตามส่วนเพิ่มเติมด้านล่าง

อัปเดต local evidence 18 ต.ค. 2026: disposable Compose integration 80 passed/81 deselected, smoke 3 passed, E2E 22 passed/1 skipped, worker/evaluator checks ผ่าน. Lesson/exam E2E ครอบคลุม refresh persistence, 375/768/1440 px, การส่งคำตอบ และสถานะ `needs_review`. ขั้นตอนเหล่านี้ไม่ใช่หลักฐาน GitHub CI, staging หรือ production.

## Coverage ที่ตรวจพบ

| Requirement | สิ่งที่มีหลักฐานใน checkout | สถานะ acceptance |
|---|---|---|
| Authentication/Guest boundary | auth routes, sessions, CSRF/Origin controls และ test suites ของ auth; [ข้อ 04](step-04-verification.md) มีผล acceptance ก่อนหน้า | ต้องตรวจซ้ำกับ SHA ปัจจุบันและ environment ก่อน release |
| Scenario/training runner/investigation | training catalog, runs/jobs, detection, tickets, analysis และ tests แยกตามโดเมน | local/CI evidence ของ SHA ปัจจุบันยังต้องยืนยัน |
| RAG/Ask AI | retrieval/citation/revocation/usage controls และ [ข้อ 14](step-14-verification.md) | ผู้ใช้ขอให้ทำ review/reconcile แล้ว; ยังรอผู้ตรวจอิสระและ provider report สำหรับ 6 unknown calls |
| Learning path | lesson/progress API, migration, Next.js page, PostgreSQL persistence/owner/gate tests และ browser refresh/responsive flow | Local acceptance ผ่าน; ยังไม่มี GitHub CI บน changes ล่าสุด หรือ accessibility audit เต็มรูปแบบ; ดู [ข้อ 15](step-15-verification.md) |
| Exam/submit/retake | exam bank, server-selected attempts, blind DTO, atomic submit และ browser exam/submit/needs_review flow | PostgreSQL integration ยืนยัน cap/rotation และ concurrent start หลัง cooldown; browser ยืนยัน cooldown rejection และเริ่ม attempt ใหม่หลัง cooldown หมด; [ข้อ 16](step-16-verification.md) |
| Grading/review/unlock | deterministic rubric, Instructor review, audit/history, concurrent review และ unlock tests | Instructor review → learner feedback ผ่าน browser และ PostgreSQL จริงใน disposable Compose; AI grading ไม่เปิด และ acceptance ข้อ 17 ยังขึ้นกับข้อ 14; [ข้อ 17](step-17-verification.md) |
| Staging/production operations | Dockerfiles, local Compose/integration harness และ health/check commands | local engine พร้อม แต่ยังไม่มี staging/registry/hosting evidence; [ข้อ 18](step-18-verification.md) ยังไม่ผ่าน |

## Acceptance flows ที่ยังรันไม่ได้ครบ

Guest → register/login → lesson progress/refresh → exam/submit → Instructor review → learner feedback หลัง refresh ผ่าน browser acceptance บน disposable Compose. Browser ตรวจ cooldown rejection และเดินจากผลตกจนเริ่ม retake ใหม่หลัง cooldown หมด. Training/investigation/RAG มี tests แยก แต่การรวม E2E บน release candidate, export coverage, accessibility audit, load targets, migration failure/rollback และ restore drill ยังไม่มีหลักฐาน staging/prod ที่ตรวจได้ในรอบนี้.

## ผลสรุป

Coverage audit นี้ชี้ช่องว่างและแหล่งหลักฐาน; ผล local ด้านบนอัปเดตแล้วแต่ยังไม่แทนการตรวจรับ end-to-end. ไม่มี URL, immutable release image digest, GitHub CI run หรือ production result ใหม่ที่อ้างได้. ข้อ 19 ยังไม่ผ่านจนกว่าข้อ 15 lesson persistence/UI, ข้อ 16–17 browser/race acceptance และข้อ 18 staging/rollback/restore จะมีผลจริง.

## ตรวจซ้ำ 21 ต.ค. 2026

บน branch `codex/retake-browser-acceptance` จาก `origin/main`, `scripts/ci-compose.sh` ผ่าน migration/health, integration **77 passed / 82 deselected**, smoke **3 passed**, worker/evaluator readiness และ browser E2E **26 passed / 1 skipped**. Browser ผ่าน Instructor review/feedback จริง และ journey จาก failed/cooldown ไปเริ่ม attempt ใหม่; PostgreSQL integration ยังยืนยัน concurrent retake start ได้ active attempt เดียว. Frontend lint/typecheck ผ่าน. GitHub CI run [39494965944](https://github.com/IMLV1/SOC/actions/runs/39494965944) ผ่านครบทุก job บน `5bfcdb2`; export/accessibility/load audits และ staging/production acceptance ยังไม่มีหลักฐาน จึงยังไม่ปิดข้อ 19.

### เอกสารต้นฉบับ: [steps-11-13-follow-up.md](steps-11-13-follow-up.md)

# ข้อ 11–13 — งานค้างที่ต้องทำต่อ

> **หมายเหตุสถานะปัจจุบัน:** การกล่าวถึง Gemini ในเอกสารนี้เป็นข้อมูลย้อนหลัง/หลักฐานของ implementation ก่อนเลือก Dify ไม่ใช่คำสั่งให้เปิดใช้หรือสถานะ provider ปัจจุบัน; repository ต้องใช้ Dify API เท่านั้น และ runtime ยังปิดจน integration ผ่านการตรวจรับ

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


อัปเดต 15 ตุลาคม 2026 หลังผู้ใช้ยืนยัน AI Studio project เป็น Free Tier แบบไม่มี billing
Gemini key ถูกเก็บใน `.local/secrets/gemini_api_key.txt`; ไม่พิมพ์/commit key
ข้อ 10 เชื่อม provider จริงแล้วเฉพาะ run ฝึก local และ synthetic events
Gemini 2.5 Flash ตอบ HTTP 404 ใน project ใหม่นี้; Google ระบุว่าจำกัด 2.5 สำหรับ project ที่เคยใช้
จึง pin Gemini 3.5 Flash-Lite ซึ่งเอกสารปัจจุบันระบุ stable, structured output และ Free Tier
real UI flow login → start S02 → worker analysis → pause/resume ผ่าน Chromium; analysis สำเร็จ
DB เก็บ mode/model/token usage และ quota reservation consumed; mock ยังคงค่าเริ่มต้น
worker รับ key ผ่าน Docker secret เฉพาะ service; test container ได้เฉพาะ DB test role secrets
Free Tier อาจนำเนื้อหาไปปรับปรุงผลิตภัณฑ์ ใช้เฉพาะ synthetic fixtures/approved generic guides
ไม่ส่ง private truth, credentials หรือข้อมูลผู้เรียนจริงไป provider
อ้างอิง [pricing](https://ai.google.dev/gemini-api/docs/pricing),
[API keys](https://ai.google.dev/gemini-api/docs/api-key),
[rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
ไฟล์นี้ติดตามงานค้างข้อ 12–13 และขอบเขตที่ยังไม่ได้อนุมัติ; ข้อ 11 ผ่าน local acceptance ตาม [ผลตรวจ](step-11-verification.md)

## Foundation ที่เพิ่มแล้ว

- fake embeddings แบบ deterministic, model fake-hash-16-v1, dimension 16, mode mock
- validation ปฏิเสธ dimension ผิด/NaN/Infinity; ไม่มี network หรือ credentials
- training incident-group metrics: duplicate/deleted/undetermined ไม่เปลี่ยน denominator,
  null พร้อมเหตุผลเมื่อตัวหารศูนย์ และรายงาน incomplete groups เมื่อ snapshot truncated
- tests ของ foundations อยู่ backend/tests/test_fake_embeddings.py และ test_evaluation_metrics.py

ผล foundation เดิม: pytest สองไฟล์ผ่าน 7 tests. ข้อ 11 เชื่อม metrics กับ evaluator/API/UI แล้วและเพิ่ม PostgreSQL/browser acceptance ตามผลตรวจด้านล่าง.
การจับ incident ใช้ evidence refs ของ detection เทียบกับ frozen expected evidence; manual tickets ไม่เข้าตัวหาร detection.

## 11 — ผ่าน local acceptance

- [x] Alembic evaluation/items และ immutable snapshot; evaluator DB grant แยก
- [x] Compose evaluator process ใช้ `evaluator_runtime`; claim, run-before-job lock และ lease fencing
- [x] finish cutoff/drain สูงสุด 60 วินาที; late analysis ถูก fence และไม่แก้ snapshot
- [x] Owner evaluation/export/completed training truth; assigned Instructor truth ก่อน finish/หลัง completion พร้อม audit; exam routes ยังไม่เปิด
- [x] Instructor account/quota/assignment สร้างผ่าน operator provisioning; comment/review ใช้ scoped API/UI และไม่แก้ assessment/note
- [x] A/B รัน detector จริงบนชุด event/truth เดียวกัน; C ส่งสถานะ unavailable จน provider/budget controls พร้อม
- [x] Next.js pending/result/export/Instructor UI; Chromium E2E finish→evaluation→JSON export ผ่าน
- [x] PostgreSQL regression ผ่าน cutoff, late AI, deleted ticket denominator, N/A metrics, grants, assignment และ immutability

ผลตรวจ 15 ต.ค. 2026: full CI integration script ผ่าน; PostgreSQL integration 50 passed,
Chromium E2E 11 passed, HTTP smoke 3 passed,
metrics/experiments 4 passed, OpenAPI approved-contract 1 passed; Ruff, mypy, ESLint และ Next typecheck ผ่าน.
มี deprecation/cache warnings ที่ไม่ทำให้ tests ล้ม. GitHub CI ยังไม่ได้รันสำหรับ changeset นี้.
Human scoring อยู่ N/A (`HUMAN_SCORING_POLICY_UNDECIDED`); rubric, retake และ override/revoke unlock ยัง pending.

## 12 — real adapter ใช้งาน local แล้ว; acceptance ข้อ 12 ยังไม่ครบ

เริ่มงานต่อบน `codex/step-12-provider-controls` จาก main หลัง PR #10 merged;
GitHub CI ของข้อ 01–11 ผ่านทั้ง 5 jobs ที่ commit `860e713` ใน
[run 38666512966](https://github.com/IMLV1/SOC/actions/runs/38666512966).
ปรับ network disconnect ให้เป็น ambiguous usage เช่น timeout เพื่อคง reservation
เป็น unknown และไม่ retry provider อัตโนมัติ. ผู้ใช้ยืนยัน global 100 requests/วัน,
200,000 tokens/วัน, 5 requests/นาที และงบ 0 บาทแล้ว.
ดูผลตรวจล่าสุดใน [รายงานข้อ 12](step-12-verification.md).

- [x] config ปฏิเสธ real mode หากไม่ยืนยัน no-billing, synthetic-only หรือ model ที่อนุมัติ
- [x] runtime secret จำกัดให้ worker; API/browser ไม่ได้รับ key
- [x] adapter ตรวจ Pydantic/citation; เก็บ token usage และคิด quota เมื่อ invalid JSON มี usage
- [x] real timeout เก็บ reservation `unknown`; timeout/invalid output/retry integration ผ่าน PostgreSQL
- [x] bounded real call จาก UI/API/worker ใช้ S02 synthetic fixture และ Gemini 3.5 Flash-Lite Free Tier
- [x] versioned Free Tier rate card, generation reservations และ global caps; PostgreSQL concurrency ผ่าน
- [x] 429 shared cooldown และ no automatic provider retry; typed adapter tests ผ่าน
- [x] operator unknown-usage reconciliation สำหรับ terminal analyses; duplicate/negative/active checks
- [x] bounded experiment C จริงหนึ่งชุด S02; เก็บ real output/usage แยก mock ตามรายงาน
- [ ] production credential/privacy controls และการ reconcile ผ่าน provider reports อัตโนมัติ (นอก local acceptance)

ข้อ 12 ตรวจรับเฉพาะ local Free Tier/synthetic/operator-triggered C; ไม่อ้าง production readiness
หรือคุณภาพ AI ทั่วไปจากชุด S02 เดียว. GitHub CI ของ branch นี้ยังรอยืนยัน.

## 13 — storage/ingestion ยังต้องทำ

- [ ] ตรวจและ pin PostgreSQL/pgvector image/extension compatibility จริง
- [ ] Alembic kb schema, profiles, fixed dimension embeddings, manifests และ runtime grants
- [ ] approved Markdown corpus แยกจาก docs/fixtures/private truth; ระบุ reviewer/license/hash
- [ ] chunking/versioned ingestion jobs พร้อม dedupe/lease/resume และ component budget
- [ ] validate-before-publish immutable release, active pointer CAS, revoke ทุก projection
- [ ] pin release/config ต่อ run ใหม่; run เก่าไม่เปลี่ยน corpus เงียบ ๆ
- [ ] golden/held-out Thai/English tests ด้วย fake embeddings; ไม่อ้าง quality benchmark จริง
- [ ] PostgreSQL tests repeat ingestion, partial publish, dimension, ACL, revoke และ upgrade

## วิธีอัปเดตสถานะ

CI integration script รันทุก test ที่ติด integration marker; foundation แยกใน backend job
เพราะต้องอ่าน docs นอก test container. ข้อ 11 ผล local ล่าสุดบันทึกในส่วนด้านบน;
GitHub CI ของ changeset นี้ยังรอยืนยัน.

เติมผลคำสั่งและหลักฐานเมื่อทดสอบผ่านจริง แล้วจึงติ๊กเฉพาะรายการนั้น
ข้อ 11 ผ่าน local acceptance; checklist ข้อ 12–13 ยังไม่ผ่าน. GitHub CI ของ changeset นี้ยังรอยืนยัน.
rubric/retake/override-revoke unlock และ global provider controls ยัง pending ตาม SRS decision register
