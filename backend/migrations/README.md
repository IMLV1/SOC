# Auth foundation migrations — step 02

Bootstrap creates roles plus app/private/ops schemas owned by migration_owner.
Run `python -m app.db.bootstrap` with the isolated administrator secret, then
`python -m app.db.migrate` with the owner secret. API/worker never migrate.
See [local setup](../../docs/local-development.md) for Compose/native commands.

0001_auth_foundation creates users, auth sessions/challenges, quotas/ledger,
assignments and append-only runtime audit. No runs, jobs, exam or KB tables yet.
Audit run_id/FK will be introduced with the run schema in step 06.

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
