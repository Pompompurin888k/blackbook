-- Migration: Add unique constraint on telegram_username for portal accounts
-- (migrated from repo root migrations/002_unique_portal_username.sql)

CREATE UNIQUE INDEX IF NOT EXISTS idx_providers_portal_username_unique
ON providers (LOWER(telegram_username))
WHERE COALESCE(auth_channel, 'telegram') = 'portal'
  AND telegram_username IS NOT NULL
  AND telegram_username <> '';
