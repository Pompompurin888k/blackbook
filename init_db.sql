-- Blackbook Database Initialization
-- Run this to create all tables manually

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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    age INT,
    height_cm INT,
    weight_kg INT,
    build VARCHAR(50),
    services JSONB,
    bio TEXT,
    nearby_places TEXT,
    availability_type VARCHAR(50),
    profile_photos JSONB,
    telegram_username VARCHAR(100),
    -- Business model columns
    subscription_tier VARCHAR(20) DEFAULT 'none',
    boost_until TIMESTAMP,
    referral_code VARCHAR(20) UNIQUE,
    referred_by BIGINT,
    referral_credits INT DEFAULT 0,
    is_premium_verified BOOLEAN DEFAULT FALSE,
    trial_used BOOLEAN DEFAULT FALSE,
    trial_started_at TIMESTAMP,
    trial_reminder_day5_sent BOOLEAN DEFAULT FALSE,
    trial_reminder_lastday_sent BOOLEAN DEFAULT FALSE,
    trial_expired_notified BOOLEAN DEFAULT FALSE
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

CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_success_reference_unique
ON payments (mpesa_reference)
WHERE status = 'SUCCESS'
  AND mpesa_reference ~ '^BB_[0-9]+_(0|3|7|30|90)_[A-Za-z0-9]+$';

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
