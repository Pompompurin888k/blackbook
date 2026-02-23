-- Add email-based authentication fields for provider portal verification.

ALTER TABLE providers
    ADD COLUMN IF NOT EXISTS email VARCHAR(255),
    ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS email_verify_code_created_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_providers_email
    ON providers (LOWER(email));
