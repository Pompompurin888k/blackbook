#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SKIP_PULL="false"
NO_BUILD="false"
RUN_R2_MIGRATION="false"
R2_MIGRATION_ARGS=""

usage() {
  cat <<'USAGE'
Usage: ./deploy.sh [options]

Options:
  --skip-pull                 Skip "git pull --ff-only origin main"
  --no-build                  Skip Docker image rebuild and run plain "up -d"
  --migrate-r2                Run R2 photo migration in dry-run mode after deploy
  --migrate-r2-apply          Run R2 photo migration with --apply after deploy
  -h, --help                  Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-pull)
      SKIP_PULL="true"
      shift
      ;;
    --no-build)
      NO_BUILD="true"
      shift
      ;;
    --migrate-r2)
      RUN_R2_MIGRATION="true"
      R2_MIGRATION_ARGS=""
      shift
      ;;
    --migrate-r2-apply)
      RUN_R2_MIGRATION="true"
      R2_MIGRATION_ARGS="--apply"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ ! -f ".env" ]]; then
  echo "Error: .env file not found in $SCRIPT_DIR"
  echo "Copy .env.example to .env and fill it first."
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "Error: docker compose/docker-compose command not found."
  exit 1
fi

echo "Project directory: $SCRIPT_DIR"

if [[ "$SKIP_PULL" != "true" ]]; then
  echo "[1/5] Pulling latest code from origin/main"
  git pull --ff-only origin main
else
  echo "[1/5] Skipping git pull (--skip-pull)"
fi

if [[ "$NO_BUILD" == "true" ]]; then
  echo "[2/5] Starting services without rebuild"
  "${COMPOSE_CMD[@]}" up -d
else
  echo "[2/5] Building and starting services"
  "${COMPOSE_CMD[@]}" up -d --build
fi

echo "[3/5] Waiting for web readiness at http://127.0.0.1:8080/health"
HEALTH_OK="false"
for _ in {1..30}; do
  if curl -fsS "http://127.0.0.1:8080/health" >/dev/null; then
    HEALTH_OK="true"
    break
  fi
  sleep 2
done

if [[ "$HEALTH_OK" != "true" ]]; then
  echo "Web health check failed. Recent web logs:"
  "${COMPOSE_CMD[@]}" logs --tail=120 web
  exit 1
fi

echo "[4/5] Container status"
"${COMPOSE_CMD[@]}" ps

echo "[5/5] Migration/startup log summary"
"${COMPOSE_CMD[@]}" logs --tail=200 web | grep -Ei "migration|database migrations|applied migration|using migration directory|error" || true

if [[ "$RUN_R2_MIGRATION" == "true" ]]; then
  echo "Running local photo migration helper ($R2_MIGRATION_ARGS)"
  "${COMPOSE_CMD[@]}" exec -T web python scripts/migrate_local_photos_to_r2.py $R2_MIGRATION_ARGS
fi

echo "Deploy completed."
