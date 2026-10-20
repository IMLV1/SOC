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
| Learning path | lesson/progress API, migration, Next.js page, PostgreSQL persistence/owner/gate tests และ browser refresh/responsive flow | Local acceptance และ GitHub CI run 39495958300 บน `c4abb42` ผ่าน; ยังขาด accessibility audit เต็มรูปแบบ; ดู [ข้อ 15](step-15-verification.md) |
| Exam/submit/retake | exam bank, server-selected attempts, blind DTO, atomic submit และ browser exam/submit/needs_review flow | PostgreSQL integration ยืนยัน cap/rotation และ concurrent start หลัง cooldown; browser ยืนยันทั้ง rejection ระหว่าง cooldownและเริ่ม attempt ใหม่หลังหมด cooldown บน disposable DB; [ข้อ 16](step-16-verification.md) |
| Grading/review/unlock | deterministic rubric, Instructor review, audit/history, concurrent review และ unlock tests | Instructor review → learner feedback ผ่าน browser และ PostgreSQL จริงใน disposable Compose; AI grading ไม่เปิด และ acceptance ข้อ 17 ยังขึ้นกับข้อ 14; [ข้อ 17](step-17-verification.md) |
| Staging/production operations | Dockerfiles, local Compose/integration harness และ health/check commands | local engine พร้อม แต่ยังไม่มี staging/registry/hosting evidence; [ข้อ 18](step-18-verification.md) ยังไม่ผ่าน |

## Acceptance flows ที่ยังรันไม่ได้ครบ

Guest → register/login → lesson progress/refresh → exam/submit → Instructor review → learner feedback หลัง refresh ผ่าน browser acceptance บน disposable Compose. Browser ตรวจ cooldown rejection และเดินต่อจากผลตกจน cooldown หมดเพื่อเริ่ม retake จริง. Training/investigation/RAG มี tests แยก แต่การรวม E2E บน release candidate, export coverage, accessibility audit, load targets, migration failure/rollback และ restore drill ยังไม่มีหลักฐาน staging/prod ที่ตรวจได้ในรอบนี้.

## ผลสรุป

Coverage audit นี้ชี้ช่องว่างและแหล่งหลักฐาน; ผล local และ GitHub CI ด้านล่างไม่ใช่การตรวจรับ staging/production. ยังไม่มี staging URL, immutable release image digest หรือ production result ใหม่ที่อ้างได้. ข้อ 19 ยังไม่ผ่านจนกว่าจะตรวจ export/accessibility/load, migration failure/rollback และ staging/restore ตามเป้าหมายได้จริง.

## ตรวจซ้ำ 21 ต.ค. 2026

บน branch `codex/retake-browser-acceptance` จาก `origin/main`, `scripts/ci-compose.sh` ผ่าน migration/health, integration **77 passed / 82 deselected**, smoke **3 passed**, worker/evaluator readiness และ browser E2E **26 passed / 1 skipped**. Browser ผ่าน Instructor review/feedback จริง และ journey จาก failed/cooldown ไปเริ่ม attempt ใหม่; PostgreSQL integration ยังยืนยัน concurrent retake start ได้ active attempt เดียว. Frontend lint/typecheck ผ่าน. GitHub CI run [39495958300](https://github.com/IMLV1/SOC/actions/runs/39495958300) ผ่านครบทุก job บน `c4abb42`; export/accessibility/load audits และ staging/production acceptance ยังไม่มีหลักฐาน จึงยังไม่ปิดข้อ 19.
