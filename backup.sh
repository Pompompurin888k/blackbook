#!/bin/bash

# Blackbook Backup Script
# Creates a backup of the database

set -e

BACKUP_DIR="/root/blackbook/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/blackbook_backup_$DATE.sql"

echo "📦 Creating backup..."

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

# Backup database
docker exec blackbook_db pg_dump -U bb_operator blackbook_db > $BACKUP_FILE

# Compress backup
gzip $BACKUP_FILE

echo "✅ Backup created: ${BACKUP_FILE}.gz"

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

echo "🗑️  Old backups cleaned up"
echo "📊 Current backups:"
ls -lh $BACKUP_DIR/*.sql.gz 2>/dev/null || echo "No backups found"
