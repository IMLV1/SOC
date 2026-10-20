# Auth foundation migrations — step 02

> This file describes the initial migration checkpoint only. The repository now has later migrations for runs, jobs, RAG, learning and exams. Check `backend/migrations/versions/` and `docs/implementation-checklist.md` for current state.

Bootstrap creates roles plus app/private/ops schemas owned by migration_owner.
Run `python -m app.db.bootstrap` with the isolated administrator secret, then
`python -m app.db.migrate` with the owner secret. API/worker never migrate.
See [local setup](../../docs/local-development.md) for Compose/native commands.

At this checkpoint, 0001_auth_foundation created users, auth sessions/challenges,
quotas/ledger, assignments and append-only runtime audit. Later revisions add
the run, job, knowledge, learning and exam schemas.

The wrapper takes transaction advisory lock 73102002 (10-second lock timeout),
verifies applied checksums and Alembic head, then applies DDL + ledger atomically.
Checksums are SHA-256 of UTF-8 source with normalized line endings for Windows/Linux.
Ledger records revision, checksum, DB timestamp and release SHA (local before release).
Direct Alembic upgrade bypass is disabled. Never edit an applied revision or stamp the
ledger to hide drift. Create a forward revision; destructive downgrade is disabled.
Nontransactional migrations need a reviewed extension to this initial runner.

Readiness requires exact head/checksums and the intended non-owner runtime role.
Future tables receive no automatic runtime grants: each migration must grant explicitly.
No runtime reads private schema in step 02; future evaluator grants must be table-scoped.
