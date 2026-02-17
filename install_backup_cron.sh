#!/usr/bin/env bash

# Installs a daily cron job for backup.sh with optional retention override.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SCRIPT="$SCRIPT_DIR/backup.sh"
SCHEDULE="${BACKUP_SCHEDULE:-20 3 * * *}"  # default: 03:20 every day
LOG_FILE="${BACKUP_LOG_FILE:-/var/log/blackbook_backup.log}"

if [[ ! -f "$BACKUP_SCRIPT" ]]; then
  echo "[cron] backup script not found: $BACKUP_SCRIPT"
  exit 1
fi

chmod +x "$BACKUP_SCRIPT"

CRON_LINE="$SCHEDULE BACKUP_RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-14} $BACKUP_SCRIPT >> $LOG_FILE 2>&1"

TMP_CRON="$(mktemp)"
crontab -l 2>/dev/null | grep -v "$BACKUP_SCRIPT" > "$TMP_CRON" || true
echo "$CRON_LINE" >> "$TMP_CRON"
crontab "$TMP_CRON"
rm -f "$TMP_CRON"

echo "[cron] installed: $CRON_LINE"
echo "[cron] current crontab:"
crontab -l
