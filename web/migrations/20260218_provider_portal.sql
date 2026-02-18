-- Provider portal support for non-Telegram onboarding.

ALTER TABLE providers
    ADD COLUMN IF NOT EXISTS auth_channel VARCHAR(20) DEFAULT 'telegram',
    ADD COLUMN IF NOT EXISTS portal_password_hash TEXT,
    ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS phone_verify_code VARCHAR(32),
    ADD COLUMN IF NOT EXISTS phone_verify_code_created_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS portal_onboarding_complete BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_providers_phone
    ON providers (phone);

CREATE INDEX IF NOT EXISTS idx_providers_auth_channel
    ON providers (auth_channel);
