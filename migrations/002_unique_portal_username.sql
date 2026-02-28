-- Migration: Add unique constraint on telegram_username for portal accounts
-- Run on server: psql -U bb_operator -d blackbook_db -f /root/blackbook/migrations/002_unique_portal_username.sql

-- Add unique partial index: enforces uniqueness only for portal accounts
-- (telegram accounts may have null or reused usernames, so we scope to portal only)
CREATE UNIQUE INDEX IF NOT EXISTS idx_providers_portal_username_unique
ON providers (LOWER(telegram_username))
WHERE COALESCE(auth_channel, 'telegram') = 'portal'
  AND telegram_username IS NOT NULL
  AND telegram_username <> '';
