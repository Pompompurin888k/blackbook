-- Ensures provider/payment schema matches the current web+bot code expectations.

CREATE TABLE IF NOT EXISTS providers (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    display_name VARCHAR(100),
    phone VARCHAR(20),
    city VARCHAR(50),
    neighborhood VARCHAR(50),
    is_verified BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT FALSE,
    is_online BOOLEAN DEFAULT FALSE,
    credits INT DEFAULT 0,
    expiry_date TIMESTAMP,
    verification_photo_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT,
    amount INT,
    mpesa_reference TEXT,
    status TEXT,
    package_days INT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS blacklist (
    id SERIAL PRIMARY KEY,
    phone VARCHAR(20) UNIQUE,
    reason TEXT,
    reported_by BIGINT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT,
    check_in_time TIMESTAMP DEFAULT NOW(),
    expected_check_back TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    admin_alerted BOOLEAN DEFAULT FALSE
);

ALTER TABLE providers
    ADD COLUMN IF NOT EXISTS age INT,
    ADD COLUMN IF NOT EXISTS height_cm INT,
    ADD COLUMN IF NOT EXISTS weight_kg INT,
    ADD COLUMN IF NOT EXISTS build VARCHAR(50),
    ADD COLUMN IF NOT EXISTS services JSONB,
    ADD COLUMN IF NOT EXISTS bio TEXT,
    ADD COLUMN IF NOT EXISTS availability_type VARCHAR(50),
    ADD COLUMN IF NOT EXISTS nearby_places TEXT,
    ADD COLUMN IF NOT EXISTS profile_photos JSONB,
    ADD COLUMN IF NOT EXISTS rate_30min INT,
    ADD COLUMN IF NOT EXISTS rate_1hr INT,
    ADD COLUMN IF NOT EXISTS rate_2hr INT,
    ADD COLUMN IF NOT EXISTS rate_3hr INT,
    ADD COLUMN IF NOT EXISTS rate_overnight INT,
    ADD COLUMN IF NOT EXISTS languages JSONB,
    ADD COLUMN IF NOT EXISTS telegram_username VARCHAR(100),
    ADD COLUMN IF NOT EXISTS subscription_tier VARCHAR(20) DEFAULT 'none',
    ADD COLUMN IF NOT EXISTS boost_until TIMESTAMP,
    ADD COLUMN IF NOT EXISTS referral_code VARCHAR(20),
    ADD COLUMN IF NOT EXISTS referred_by BIGINT,
    ADD COLUMN IF NOT EXISTS referral_credits INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS is_premium_verified BOOLEAN DEFAULT FALSE;

CREATE UNIQUE INDEX IF NOT EXISTS idx_providers_referral_code_unique
ON providers (referral_code)
WHERE referral_code IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_success_reference_unique
ON payments (mpesa_reference)
WHERE status = 'SUCCESS'
  AND mpesa_reference ~ '^BB_[0-9]+_(0|3|7|30|90)_[A-Za-z0-9]+$';
