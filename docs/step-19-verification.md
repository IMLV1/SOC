# ผลตรวจข้อ 19 — requirement coverage และ acceptance gaps

ตรวจ source/docs ใน branch `implementation-checklist` วันที่ 17 ตุลาคม 2026 เป็น coverage audit ไม่ใช่ final acceptance, production release หรือ deployment report

อัปเดต local evidence 18 ต.ค. 2026: disposable Compose integration 80 passed/81 deselected, smoke 3 passed, E2E 22 passed/1 skipped, worker/evaluator checks ผ่าน. Lesson/exam E2E ครอบคลุม refresh persistence, 375/768/1440 px, การส่งคำตอบ และสถานะ `needs_review`. ขั้นตอนเหล่านี้ไม่ใช่หลักฐาน GitHub CI, staging หรือ production.

## Coverage ที่ตรวจพบ

| Requirement | สิ่งที่มีหลักฐานใน checkout | สถานะ acceptance |
|---|---|---|
| Authentication/Guest boundary | auth routes, sessions, CSRF/Origin controls และ test suites ของ auth; [ข้อ 04](step-04-verification.md) มีผล acceptance ก่อนหน้า | ต้องตรวจซ้ำกับ SHA ปัจจุบันและ environment ก่อน release |
| Scenario/training runner/investigation | training catalog, runs/jobs, detection, tickets, analysis และ tests แยกตามโดเมน | local/CI evidence ของ SHA ปัจจุบันยังต้องยืนยัน |
| RAG/Ask AI | retrieval/citation/revocation/usage controls และ [ข้อ 14](step-14-verification.md) | ผู้ใช้ขอให้ทำ review/reconcile แล้ว; ยังรอผู้ตรวจอิสระและ provider report สำหรับ 6 unknown calls |
| Learning path | lesson/progress API, migration, Next.js page, PostgreSQL persistence/owner/gate tests และ browser refresh/responsive flow | Local acceptance ผ่าน; ยังไม่มี GitHub CI บน changes ล่าสุด หรือ accessibility audit เต็มรูปแบบ; ดู [ข้อ 15](step-15-verification.md) |
| Exam/submit/retake | exam bank, server-selected attempts, blind DTO, atomic submit และ browser exam/submit/needs_review flow | concurrent submit และ retake cap/case rotation ผ่าน PostgreSQL integration; ยังขาด retake race test และ browser flow; [ข้อ 16](step-16-verification.md) |
| Grading/review/unlock | deterministic rubric, Instructor review, audit/history, concurrent review และ unlock tests | ยังขาด browser feedback/review flow และ AI grading ไม่เปิด; [ข้อ 17](step-17-verification.md) |
| Staging/production operations | Dockerfiles, local Compose/integration harness และ health/check commands | local engine พร้อม แต่ยังไม่มี staging/registry/hosting evidence; [ข้อ 18](step-18-verification.md) ยังไม่ผ่าน |

## Acceptance flows ที่ยังรันไม่ได้ครบ

Guest → register/login → lesson progress/refresh และเริ่มข้อสอบ/submit ผ่าน local browser acceptance แล้ว. Feedback หลัง Instructor review และ retake browser flow/tests ยังขาด. Training/investigation/RAG มี tests แยก แต่การรวม E2E บน release candidate, export coverage, accessibility audit, load targets, migration failure/rollback และ restore drill ยังไม่มีหลักฐาน staging/prod ที่ตรวจได้ในรอบนี้.

## ผลสรุป

Coverage audit นี้ชี้ช่องว่างและแหล่งหลักฐาน; ผล local ด้านบนอัปเดตแล้วแต่ยังไม่แทนการตรวจรับ end-to-end. ไม่มี URL, immutable release image digest, GitHub CI run หรือ production result ใหม่ที่อ้างได้. ข้อ 19 ยังไม่ผ่านจนกว่าข้อ 15 lesson persistence/UI, ข้อ 16–17 browser/race acceptance และข้อ 18 staging/rollback/restore จะมีผลจริง.
