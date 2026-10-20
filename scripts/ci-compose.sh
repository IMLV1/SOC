#!/usr/bin/env bash
set -euo pipefail

# Cleanup must never target the developer's soc-local stack/volume.
case "${COMPOSE_PROJECT_NAME:-}" in
  soc-ci-?*) ;;
  *) echo 'Set an isolated COMPOSE_PROJECT_NAME beginning soc-ci-.' >&2; exit 2 ;;
esac
: "${SOC_API_PORT:=18000}" "${SOC_WEB_PORT:=13000}" "${SOC_DB_PORT:=55438}"
export SOC_API_PORT SOC_WEB_PORT SOC_DB_PORT
# A developer's .env may enable the real provider. CI is always offline;
# real acceptance uses the separate explicit operator command.
export SOC_AI_PROVIDER=mock
export GOOGLE_OAUTH_ENABLED=false
# The baseline browser stack has no published KB; RAG integration tests prepare their own.
export SOC_KB_ENABLED=false
cleanup() {
  docker compose --profile test down --volumes --remove-orphans
  if [[ -n "${soc_ci_instructor_password_file:-}" ]]; then
    rm -f "$soc_ci_instructor_password_file"
  fi
}
trap cleanup EXIT
docker compose config --quiet
docker compose build
docker compose up -d --wait --wait-timeout 120
docker compose exec -T api python -c "from pathlib import Path; assert not Path('/app/fixtures').exists()"
docker compose exec -T worker python -c "from pathlib import Path; assert Path('/app/fixtures/events/training/s02-v1.json').is_file(); assert Path('/app/fixtures/events/exam/e01-v1.json').is_file(); assert not Path('/app/fixtures/ground-truth').exists(); assert not Path('/app/fixtures/exam/ground-truth.json').exists(); assert not Path('/app/fixtures/exam/catalog.json').exists(); assert not Path('/app/fixtures/catalog.json').exists()"
docker compose exec -T frontend node -e "const fs=require('fs'); if(fs.existsSync('/app/fixtures')||fs.existsSync('/app/backend'))process.exit(1)"
mkdir -p test-results
# Only synthetic JUnit reports; permit the test container's non-root UID to write them.
chmod 777 test-results
reports_dir="$PWD/test-results"
if command -v cygpath >/dev/null 2>&1; then
  reports_dir="$(cygpath -m "$reports_dir")"
  export MSYS_NO_PATHCONV=1
fi
docker compose --profile test run --build --rm -T \
  -v "$reports_dir:/reports" test \
  python -m pytest tests --ignore=tests/test_foundation.py -m integration -q -p no:cacheprovider --junitxml=/reports/integration.xml
SOC_SMOKE_ORIGIN="http://127.0.0.1:$SOC_WEB_PORT" SOC_EXPECT_READY_STATUS=200 \
  node --test frontend/tests/smoke.test.mjs
docker compose exec -T worker python -m app.worker --check
docker compose exec -T evaluator python -m app.evaluation --check
# Provision a short-lived Instructor only in the disposable CI database. The
# browser E2E assigns each newly registered learner through the operator CLI.
export SOC_TEST_INSTRUCTOR_EMAIL="soc-ci-instructor@example.test"
export SOC_TEST_INSTRUCTOR_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
soc_ci_instructor_password_file="$(mktemp)"
printf '%s' "$SOC_TEST_INSTRUCTOR_PASSWORD" > "$soc_ci_instructor_password_file"
instructor_result="$(docker compose run --rm -T --no-deps \
  -v "$soc_ci_instructor_password_file:/tmp/soc-ci-instructor-password:ro" seed \
  python -m app.db.provision user \
  --email "$SOC_TEST_INSTRUCTOR_EMAIL" \
  --display-name 'CI Exam Instructor' \
  --role instructor \
  --daily-runs 0 \
  --daily-ai-requests 0 \
  --password-file /tmp/soc-ci-instructor-password)"
export SOC_TEST_INSTRUCTOR_ID="${instructor_result#Account ready: }"
export SOC_REPO_ROOT="$PWD"
SOC_SMOKE_ORIGIN="http://127.0.0.1:$SOC_WEB_PORT" npm --prefix frontend run test:e2e
