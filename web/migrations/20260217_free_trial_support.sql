-- Adds one-time free trial support fields for providers.

ALTER TABLE providers
    ADD COLUMN IF NOT EXISTS trial_used BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS trial_started_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS trial_reminder_day5_sent BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS trial_reminder_lastday_sent BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS trial_expired_notified BOOLEAN DEFAULT FALSE;
