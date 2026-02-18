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
    auth_channel VARCHAR(20) DEFAULT 'telegram',
    portal_password_hash TEXT,
    phone_verified BOOLEAN DEFAULT FALSE,
    phone_verify_code VARCHAR(32),
    phone_verify_code_created_at TIMESTAMP,
    portal_onboarding_complete BOOLEAN DEFAULT FALSE,
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
    trial_reminder_day2_sent BOOLEAN DEFAULT FALSE,
    trial_reminder_day5_sent BOOLEAN DEFAULT FALSE,
    trial_reminder_lastday_sent BOOLEAN DEFAULT FALSE,
    trial_expired_notified BOOLEAN DEFAULT FALSE,
    trial_winback_sent BOOLEAN DEFAULT FALSE
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

CREATE TABLE IF NOT EXISTS bot_funnel_events (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    event_name VARCHAR(64) NOT NULL,
    event_payload JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lead_analytics (
    id BIGSERIAL PRIMARY KEY,
    provider_id INT NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    client_ip TEXT,
    device_type VARCHAR(20),
    contact_method VARCHAR(20) NOT NULL,
    is_stealth BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
