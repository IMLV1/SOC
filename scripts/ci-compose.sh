#!/usr/bin/env bash
set -euo pipefail

# Cleanup must never target the developer's soc-local stack/volume.
case "${COMPOSE_PROJECT_NAME:-}" in
  soc-ci-?*) ;;
  *) echo 'Set an isolated COMPOSE_PROJECT_NAME beginning soc-ci-.' >&2; exit 2 ;;
esac
: "${SOC_API_PORT:=18000}" "${SOC_WEB_PORT:=13000}" "${SOC_DB_PORT:=55438}"
export SOC_API_PORT SOC_WEB_PORT SOC_DB_PORT
cleanup() {
  docker compose --profile test down --volumes --remove-orphans
}
trap cleanup EXIT
docker compose config --quiet
docker compose build
docker compose up -d --wait --wait-timeout 120
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
  python -m pytest tests/test_database.py -q -p no:cacheprovider --junitxml=/reports/integration.xml
SOC_SMOKE_ORIGIN="http://127.0.0.1:$SOC_WEB_PORT" SOC_EXPECT_READY_STATUS=200 \
  node --test frontend/tests/smoke.test.mjs
docker compose exec -T worker python -m app.worker --check
