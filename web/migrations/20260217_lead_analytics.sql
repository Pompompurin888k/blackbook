-- Tracks contact intent clicks before redirecting users to WhatsApp or phone.

CREATE TABLE IF NOT EXISTS lead_analytics (
    id BIGSERIAL PRIMARY KEY,
    provider_id INT NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    client_ip TEXT,
    device_type VARCHAR(20),
    contact_method VARCHAR(20) NOT NULL,
    is_stealth BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lead_analytics_provider_id
    ON lead_analytics (provider_id);

CREATE INDEX IF NOT EXISTS idx_lead_analytics_created_at
    ON lead_analytics (created_at DESC);
