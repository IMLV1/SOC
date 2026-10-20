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
