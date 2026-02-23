-- Impact summary:
-- Adds dedicated password-reset code fields for portal email/password auth.
-- Rollback note:
-- Drop these columns if rollback is required:
--   ALTER TABLE providers DROP COLUMN IF EXISTS password_reset_code_hash;
--   ALTER TABLE providers DROP COLUMN IF EXISTS password_reset_code_expires_at;
--   ALTER TABLE providers DROP COLUMN IF EXISTS password_reset_code_used_at;

ALTER TABLE providers
    ADD COLUMN IF NOT EXISTS password_reset_code_hash TEXT,
    ADD COLUMN IF NOT EXISTS password_reset_code_expires_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS password_reset_code_used_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_providers_password_reset_expires
    ON providers (password_reset_code_expires_at);
