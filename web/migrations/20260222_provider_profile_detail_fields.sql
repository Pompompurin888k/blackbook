-- Adds provider profile detail fields used by the public profile page and portal onboarding.

ALTER TABLE providers
    ADD COLUMN IF NOT EXISTS gender VARCHAR(20),
    ADD COLUMN IF NOT EXISTS sexual_orientation VARCHAR(32),
    ADD COLUMN IF NOT EXISTS nationality VARCHAR(64),
    ADD COLUMN IF NOT EXISTS county VARCHAR(64),
    ADD COLUMN IF NOT EXISTS incalls_from INT,
    ADD COLUMN IF NOT EXISTS outcalls_from INT,
    ADD COLUMN IF NOT EXISTS video_url TEXT;
