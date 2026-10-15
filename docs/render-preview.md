# Render Free preview — deployment preparation

Scope: Next.js standalone + FastAPI on two Free web services, mock AI.
User approved signup/login + PostgreSQL; background work is disabled in auth-only mode.
No paid workers/private services/disks or automatic deployment are included.

Render workspace: My Workspace. Free PostgreSQL `soc-preview-db` created on 15 October
2026, PostgreSQL 17, Singapore, expires 14 November 2026. Web services pending.
Proposed region: Singapore. Select Free explicitly for every service.

| Setting | API | Frontend |
|---|---|---|
| Repository | IMLV1/SOC | IMLV1/SOC |
| Branch | codex/step-12-provider-controls | codex/step-12-provider-controls |
| Docker context | backend | frontend |
| Dockerfile | backend/Dockerfile (final api target) | frontend/Dockerfile |
| Health check | /health/live | /health/live (proxies API) |
| AI provider | SOC_AI_PROVIDER=mock | no provider credential |
| Auto-deploy | off | off |
| Preview guard | SOC_PREVIEW_MODE=auth_only | SOC_PREVIEW_MODE=auth_only (build arg and runtime) |

The preview API rejects non-auth mutations with 503 PREVIEW_UNAVAILABLE, so a
direct API call cannot queue work that has no worker. The UI disables run start
and shows a temporary-database/mock-AI notice. This is not runner acceptance.

Operator preparation (not performed by API startup): save the external database
URL to ignored `.local/render-preview/admin-url.txt`, then from `backend/` run
`.venv/Scripts/python.exe -m app.db.render_preview --directory ../.local/render-preview`.
This verifies external TLS, creates independent role passwords, runs the same
checksummed migrations and seeds the training catalog. Its output suppresses
credentials and SQL. Managed-role compatibility must pass before deploying API.
Copy nonsecret coordinates from generated `runtime.env` to API environment;
add only `api_runtime.txt` using Render Secret Files. Alternatively import generated
ignored `api-secret.env` with Render's Add from .env file picker. This sets only
`DB_PASSWORD` as an encrypted service environment secret; omit `DB_PASSWORD_FILE`.
The API rejects conflicting sources and requires 24+ characters without defaults.
Do not upload owner/admin files. Do not enable environment logging or echo secrets.

Verification on 15 October 2026: managed database bootstrap, migration ledger
readiness and catalog seed passed. API runtime cannot create app objects. Bootstrap
rejects existing elevated roles instead of attempting superuser-only ALTER flags.
Local regression: 52 unit/contract tests, 55 PostgreSQL integration tests, 11 browser
E2E tests, 3 HTTP smoke tests, lint/typecheck/build and client asset guard passed.
HTTPS signup/login/logout acceptance remains pending web-service deployment.

Deploy API first. Set frontend `BACKEND_ORIGIN` to the actual HTTPS API public URL
before its Docker build; Next rewrites compile this value during build.
Free API services cannot receive private-network traffic, so an internal Render
hostname is unsuitable for this pair of Free services.
Keep AUTH_COOKIE_SECURE=true and use the actual frontend origin for AUTH_ORIGINS.
Never upload local `.env`/secrets or reuse local database credentials.

Free services sleep after 15 minutes idle; workspace free hours are shared.
Free PostgreSQL expires after 30 days and has no backups. Free services have no
one-off job/shell feature, so database role bootstrap/migration must be a separate
explicit operator step; API must not run with owner credentials.
Full runner continuity and production readiness cannot be accepted on this preview.

Sources checked 15 October 2026:
[Render Free](https://render.com/docs/free),
[Docker deployment](https://render.com/docs/docker),
[Blueprint specification](https://render.com/docs/blueprint-spec).
