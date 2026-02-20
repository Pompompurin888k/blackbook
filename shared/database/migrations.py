import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from pathlib import Path
from .base import BaseRepository

logger = logging.getLogger(__name__)

class MigrationsRepository(BaseRepository):
    """Repository for migrations operations."""

    def init_tables(self):
            """Creates all tables if they don't exist. Zero-manual-setup deployment."""
            providers_query = """
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
                telegram_username VARCHAR(100)
            );
            """

            payments_query = """
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT,
                amount INT,
                mpesa_reference TEXT,
                status TEXT,
                package_days INT,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """

            payment_reference_index_query = """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_success_reference_unique
            ON payments (mpesa_reference)
            WHERE status = 'SUCCESS'
              AND mpesa_reference ~ '^BB_[0-9]+_(0|3|7|30|90)_[A-Za-z0-9]+$';
            """

            # Blacklist table for safety checks
            blacklist_query = """
            CREATE TABLE IF NOT EXISTS blacklist (
                id SERIAL PRIMARY KEY,
                phone VARCHAR(20) UNIQUE,
                reason TEXT,
                reported_by BIGINT,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """

            # Active sessions table for safety timer
            sessions_query = """
            CREATE TABLE IF NOT EXISTS sessions (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT,
                check_in_time TIMESTAMP DEFAULT NOW(),
                expected_check_back TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                admin_alerted BOOLEAN DEFAULT FALSE
            );
            """

            funnel_events_query = """
            CREATE TABLE IF NOT EXISTS bot_funnel_events (
                id BIGSERIAL PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                event_name VARCHAR(64) NOT NULL,
                event_payload JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """

            lead_analytics_query = """
            CREATE TABLE IF NOT EXISTS lead_analytics (
                id BIGSERIAL PRIMARY KEY,
                provider_id INT NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
                client_ip TEXT,
                device_type VARCHAR(20),
                contact_method VARCHAR(20) NOT NULL,
                is_stealth BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """

            verification_events_query = """
            CREATE TABLE IF NOT EXISTS provider_verification_events (
                id BIGSERIAL PRIMARY KEY,
                provider_id INT NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
                event_type VARCHAR(64) NOT NULL,
                event_payload JSONB,
                admin_telegram_id BIGINT,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """

            # Add new columns if they don't exist
            add_columns = """
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='phone') THEN
                    ALTER TABLE providers ADD COLUMN phone VARCHAR(20);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='is_online') THEN
                    ALTER TABLE providers ADD COLUMN is_online BOOLEAN DEFAULT FALSE;
                END IF;

                -- PROFESSIONAL PORTFOLIO COLUMNS
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='age') THEN
                    ALTER TABLE providers ADD COLUMN age INT;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='height_cm') THEN
                    ALTER TABLE providers ADD COLUMN height_cm INT;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='weight_kg') THEN
                    ALTER TABLE providers ADD COLUMN weight_kg INT;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='build') THEN
                    ALTER TABLE providers ADD COLUMN build VARCHAR(50);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='services') THEN
                    ALTER TABLE providers ADD COLUMN services JSONB;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='bio') THEN
                    ALTER TABLE providers ADD COLUMN bio TEXT;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='availability_type') THEN
                    ALTER TABLE providers ADD COLUMN availability_type VARCHAR(50);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='nearby_places') THEN
                    ALTER TABLE providers ADD COLUMN nearby_places TEXT;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='profile_photos') THEN
                    ALTER TABLE providers ADD COLUMN profile_photos JSONB;
                END IF;

                -- HOURLY RATES
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='rate_30min') THEN
                    ALTER TABLE providers ADD COLUMN rate_30min INT;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='rate_1hr') THEN
                    ALTER TABLE providers ADD COLUMN rate_1hr INT;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='rate_2hr') THEN
                    ALTER TABLE providers ADD COLUMN rate_2hr INT;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='rate_3hr') THEN
                    ALTER TABLE providers ADD COLUMN rate_3hr INT;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='rate_overnight') THEN
                    ALTER TABLE providers ADD COLUMN rate_overnight INT;
                END IF;

                -- LANGUAGES SPOKEN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='languages') THEN
                    ALTER TABLE providers ADD COLUMN languages JSONB;
                END IF;

                -- TELEGRAM USERNAME
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='telegram_username') THEN
                    ALTER TABLE providers ADD COLUMN telegram_username VARCHAR(100);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='auth_channel') THEN
                    ALTER TABLE providers ADD COLUMN auth_channel VARCHAR(20) DEFAULT 'telegram';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='portal_password_hash') THEN
                    ALTER TABLE providers ADD COLUMN portal_password_hash TEXT;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='phone_verified') THEN
                    ALTER TABLE providers ADD COLUMN phone_verified BOOLEAN DEFAULT FALSE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='phone_verify_code') THEN
                    ALTER TABLE providers ADD COLUMN phone_verify_code VARCHAR(32);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='phone_verify_code_created_at') THEN
                    ALTER TABLE providers ADD COLUMN phone_verify_code_created_at TIMESTAMP;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='portal_onboarding_complete') THEN
                    ALTER TABLE providers ADD COLUMN portal_onboarding_complete BOOLEAN DEFAULT FALSE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='account_state') THEN
                    ALTER TABLE providers ADD COLUMN account_state VARCHAR(20) DEFAULT 'approved';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='verification_code_hash') THEN
                    ALTER TABLE providers ADD COLUMN verification_code_hash TEXT;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='verification_code_expires_at') THEN
                    ALTER TABLE providers ADD COLUMN verification_code_expires_at TIMESTAMP;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='verification_code_used_at') THEN
                    ALTER TABLE providers ADD COLUMN verification_code_used_at TIMESTAMP;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='approved_by_admin') THEN
                    ALTER TABLE providers ADD COLUMN approved_by_admin BIGINT;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='approved_at') THEN
                    ALTER TABLE providers ADD COLUMN approved_at TIMESTAMP;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='rejection_reason') THEN
                    ALTER TABLE providers ADD COLUMN rejection_reason TEXT;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='login_failed_attempts') THEN
                    ALTER TABLE providers ADD COLUMN login_failed_attempts INT DEFAULT 0;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='locked_until') THEN
                    ALTER TABLE providers ADD COLUMN locked_until TIMESTAMP;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='last_login_attempt_at') THEN
                    ALTER TABLE providers ADD COLUMN last_login_attempt_at TIMESTAMP;
                END IF;

                -- BUSINESS MODEL COLUMNS
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='subscription_tier') THEN
                    ALTER TABLE providers ADD COLUMN subscription_tier VARCHAR(20) DEFAULT 'none';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='boost_until') THEN
                    ALTER TABLE providers ADD COLUMN boost_until TIMESTAMP;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='referral_code') THEN
                    ALTER TABLE providers ADD COLUMN referral_code VARCHAR(20) UNIQUE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='referred_by') THEN
                    ALTER TABLE providers ADD COLUMN referred_by BIGINT;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='referral_credits') THEN
                    ALTER TABLE providers ADD COLUMN referral_credits INT DEFAULT 0;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='is_premium_verified') THEN
                    ALTER TABLE providers ADD COLUMN is_premium_verified BOOLEAN DEFAULT FALSE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='trial_used') THEN
                    ALTER TABLE providers ADD COLUMN trial_used BOOLEAN DEFAULT FALSE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='trial_started_at') THEN
                    ALTER TABLE providers ADD COLUMN trial_started_at TIMESTAMP;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='trial_reminder_day2_sent') THEN
                    ALTER TABLE providers ADD COLUMN trial_reminder_day2_sent BOOLEAN DEFAULT FALSE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='trial_reminder_day5_sent') THEN
                    ALTER TABLE providers ADD COLUMN trial_reminder_day5_sent BOOLEAN DEFAULT FALSE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='trial_reminder_lastday_sent') THEN
                    ALTER TABLE providers ADD COLUMN trial_reminder_lastday_sent BOOLEAN DEFAULT FALSE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='trial_expired_notified') THEN
                    ALTER TABLE providers ADD COLUMN trial_expired_notified BOOLEAN DEFAULT FALSE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='trial_winback_sent') THEN
                    ALTER TABLE providers ADD COLUMN trial_winback_sent BOOLEAN DEFAULT FALSE;
                END IF;
            END $$;
            """

            try:
                with self.conn.cursor() as cur:
                    cur.execute(providers_query)
                    cur.execute(payments_query)
                    cur.execute(payment_reference_index_query)
                    cur.execute(blacklist_query)
                    cur.execute(sessions_query)
                    cur.execute(funnel_events_query)
                    cur.execute(lead_analytics_query)
                    cur.execute(verification_events_query)
                    cur.execute(add_columns)
                    cur.execute("""
                        UPDATE providers
                        SET account_state = CASE
                            WHEN COALESCE(auth_channel, 'telegram') = 'portal' AND COALESCE(is_verified, FALSE) = FALSE THEN 'pending_review'
                            WHEN COALESCE(is_verified, FALSE) = TRUE THEN 'approved'
                            ELSE 'approved'
                        END
                        WHERE account_state IS NULL
                           OR account_state NOT IN ('pending_review', 'approved', 'rejected', 'suspended')
                    """)
                    self.conn.commit()
                    logger.info("🛠️ Database tables initialized.")
            except Exception as e:
                logger.error(f"❌ Failed to initialize tables: {e}")
                try:
                    self.conn.rollback()
                except Exception:
                    pass

    def _run_startup_migrations(self):
            """Runs idempotent SQL migrations so deploys stay schema-compatible."""
            migration_dir = Path(__file__).resolve().parent / "migrations"
            if not migration_dir.exists():
                logger.info("No migration directory found; skipping startup migrations.")
                return

            try:
                with self.conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS schema_migrations (
                            id BIGSERIAL PRIMARY KEY,
                            migration_key VARCHAR(255) UNIQUE NOT NULL,
                            applied_at TIMESTAMP DEFAULT NOW()
                        )
                    """)
                    self.conn.commit()
            except Exception as e:
                logger.error(f"❌ Failed to initialize schema_migrations table: {e}")
                self.conn.rollback()
                raise

            for migration_path in sorted(migration_dir.glob("*.sql")):
                migration_key = migration_path.name
                try:
                    with self.conn.cursor() as cur:
                        cur.execute(
                            "SELECT 1 FROM schema_migrations WHERE migration_key = %s",
                            (migration_key,),
                        )
                        already_applied = cur.fetchone() is not None
                        if already_applied:
                            continue

                        sql = migration_path.read_text(encoding="utf-8")
                        cur.execute(sql)
                        cur.execute(
                            "INSERT INTO schema_migrations (migration_key) VALUES (%s)",
                            (migration_key,),
                        )
                    self.conn.commit()
                    logger.info(f"✅ Applied migration: {migration_key}")
                except Exception as e:
                    logger.error(f"❌ Migration failed ({migration_key}): {e}")
                    self.conn.rollback()
                    raise

