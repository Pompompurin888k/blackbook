#!/usr/bin/env bash

# Blackbook DB backup script with retention.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$SCRIPT_DIR}"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
DB_CONTAINER="${DB_CONTAINER:-blackbook_db}"
DB_USER="${DB_USER:-bb_operator}"
DB_NAME="${DB_NAME:-blackbook_db}"

DATE="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/blackbook_backup_$DATE.sql"

echo "[backup] creating backup in $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP_FILE"
gzip "$BACKUP_FILE"

echo "[backup] created: ${BACKUP_FILE}.gz"
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +"$RETENTION_DAYS" -delete

echo "[backup] pruned backups older than $RETENTION_DAYS day(s)"
echo "[backup] current files:"
ls -lh "$BACKUP_DIR"/*.sql.gz 2>/dev/null || echo "[backup] no backups yet"
