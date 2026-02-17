-- Adds additional retention-tracking fields for trial reminders and winback.

ALTER TABLE providers
    ADD COLUMN IF NOT EXISTS trial_reminder_day2_sent BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS trial_winback_sent BOOLEAN DEFAULT FALSE;
