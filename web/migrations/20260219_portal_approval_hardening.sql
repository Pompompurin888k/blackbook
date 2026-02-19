-- Harden portal onboarding approval flow with account-state gating and audit trails.

ALTER TABLE providers
    ADD COLUMN IF NOT EXISTS account_state VARCHAR(20),
    ADD COLUMN IF NOT EXISTS verification_code_hash TEXT,
    ADD COLUMN IF NOT EXISTS verification_code_expires_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS verification_code_used_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS approved_by_admin BIGINT,
    ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS rejection_reason TEXT,
    ADD COLUMN IF NOT EXISTS login_failed_attempts INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP,
    ADD COLUMN IF NOT EXISTS last_login_attempt_at TIMESTAMP;

UPDATE providers
SET account_state = CASE
    WHEN COALESCE(auth_channel, 'telegram') = 'portal' AND COALESCE(is_verified, FALSE) = FALSE THEN 'pending_review'
    WHEN COALESCE(is_verified, FALSE) = TRUE THEN 'approved'
    ELSE 'approved'
END
WHERE account_state IS NULL
   OR account_state NOT IN ('pending_review', 'approved', 'rejected', 'suspended');

ALTER TABLE providers
    ALTER COLUMN account_state SET DEFAULT 'approved';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'providers_account_state_check'
    ) THEN
        ALTER TABLE providers
            ADD CONSTRAINT providers_account_state_check
            CHECK (account_state IN ('pending_review', 'approved', 'rejected', 'suspended'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_providers_account_state
    ON providers (account_state);

CREATE INDEX IF NOT EXISTS idx_providers_locked_until
    ON providers (locked_until);

CREATE TABLE IF NOT EXISTS provider_verification_events (
    id BIGSERIAL PRIMARY KEY,
    provider_id INT NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    event_type VARCHAR(64) NOT NULL,
    event_payload JSONB,
    admin_telegram_id BIGINT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_provider_verification_events_provider_time
    ON provider_verification_events (provider_id, created_at DESC);

