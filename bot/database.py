import os
import time
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from datetime import datetime, timedelta
import logging

# Setup Logging so you can see what's happening in 'docker logs blackbook_bot'
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.host = os.getenv("DB_HOST", "db")
        self.database = os.getenv("DB_NAME", "blackbook_db")
        self.user = os.getenv("DB_USER", "bb_operator")
        self.password = os.getenv("DB_PASSWORD")
        self.port = os.getenv("DB_PORT", "5432")
        self.db_timezone = os.getenv("DB_TIMEZONE", "Africa/Nairobi")
        self.conn = self.connect_with_retry()
        self.init_tables()

    def connect_with_retry(self):
        """Attempts to connect to Postgres. Retries every 2 seconds if DB is still booting."""
        while True:
            try:
                conn = psycopg2.connect(
                    host=self.host,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                    port=self.port,
                    options=f"-c timezone={self.db_timezone}",
                    cursor_factory=RealDictCursor
                )
                logger.info("✅ Successfully connected to the Blackbook Vault.")
                return conn
            except psycopg2.OperationalError:
                logger.info("⏳ Database is booting up... retrying in 2 seconds.")
                time.sleep(2)

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

    # ==================== PROVIDER METHODS ====================
    
    def _ensure_connection(self):
        """Checks if the database connection is alive and reconnects if needed."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            logger.warning("⚠️ Database connection lost. Reconnecting...")
            self.conn = self.connect_with_retry()

    def get_provider(self, tg_id):
        """Fetch a specific provider by Telegram ID with all profile fields."""
        self._ensure_connection()
        query = "SELECT * FROM providers WHERE telegram_id = %s"
        with self.conn.cursor() as cur:
            cur.execute(query, (tg_id,))
            return cur.fetchone()

    def add_provider(self, tg_id, name):
        """Initial registration. Uses ON CONFLICT to avoid duplicate errors."""
        query = """
        INSERT INTO providers (telegram_id, display_name) 
        VALUES (%s, %s) 
        ON CONFLICT (telegram_id) DO NOTHING
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (tg_id, name))
                self.conn.commit()
        except Exception as e:
            logger.error(f"❌ Error adding provider: {e}")
            self.conn.rollback()

    def update_provider_profile(self, tg_id, data: dict):
        """
        Updates provider profile details.
        Accepts a dictionary of fields to update to allow flexible partial updates.
        """
        if not data:
            return

        allowed_fields = {
            "display_name", "phone", "city", "neighborhood",
            "is_verified", "is_active", "is_online", "credits", "expiry_date",
            "verification_photo_id", "telegram_username",
            "age", "height_cm", "weight_kg", "build", "services", "bio",
            "availability_type", "nearby_places", "profile_photos",
            "rate_30min", "rate_1hr", "rate_2hr", "rate_3hr", "rate_overnight",
            "languages", "subscription_tier", "boost_until", "referral_code",
            "referred_by", "referral_credits", "is_premium_verified",
            "trial_used", "trial_started_at", "trial_reminder_day2_sent",
            "trial_reminder_day5_sent", "trial_reminder_lastday_sent",
            "trial_expired_notified", "trial_winback_sent",
            "phone_verified", "phone_verify_code", "phone_verify_code_created_at",
            "account_state", "verification_code_hash", "verification_code_expires_at",
            "verification_code_used_at", "approved_by_admin", "approved_at",
            "rejection_reason", "login_failed_attempts", "locked_until", "last_login_attempt_at"
        }

        sanitized_data = {k: v for k, v in data.items() if k in allowed_fields}
        if not sanitized_data:
            logger.warning(f"⚠️ Ignored profile update for {tg_id}: no allowed fields in payload")
            return
            
        # Build dynamic query
        set_clauses = []
        values = []
        
        for key, value in sanitized_data.items():
            set_clauses.append(f"{key} = %s")
            values.append(value)
            
        values.append(tg_id) # For WHERE clause
        
        query = f"UPDATE providers SET {', '.join(set_clauses)} WHERE telegram_id = %s"
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, tuple(values))
                self.conn.commit()
                logger.info(f"✅ Updated profile for {tg_id}: {list(sanitized_data.keys())}")
        except Exception as e:
            logger.error(f"❌ Error updating profile: {e}")
            self.conn.rollback()

    def update_provider_phone(self, tg_id, phone):
        """Updates provider's phone number."""
        query = "UPDATE providers SET phone = %s WHERE telegram_id = %s"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (phone, tg_id))
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ Error updating phone: {e}")
            self.conn.rollback()
            return False

    def get_provider_phone(self, tg_id):
        """Gets provider's phone number for STK push."""
        query = "SELECT phone FROM providers WHERE telegram_id = %s"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (tg_id,))
                result = cur.fetchone()
                return result["phone"] if result else None
        except Exception as e:
            logger.error(f"❌ Error getting phone: {e}")
            return None

    def save_verification_photo(self, tg_id, photo_id):
        """Saves the verification photo file ID."""
        query = "UPDATE providers SET verification_photo_id = %s WHERE telegram_id = %s"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (photo_id, tg_id))
                self.conn.commit()
        except Exception as e:
            logger.error(f"❌ Error saving verification photo: {e}")
            self.conn.rollback()
    
    def save_provider_photos(self, tg_id, photo_ids: list):
        """Saves provider's profile photos as JSON array."""
        import json
        photos_json = json.dumps(photo_ids)
        query = "UPDATE providers SET profile_photos = %s WHERE telegram_id = %s"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (photos_json, tg_id))
                self.conn.commit()
                logger.info(f"✅ Saved {len(photo_ids)} photos for provider {tg_id}")
        except Exception as e:
            logger.error(f"❌ Error saving provider photos: {e}")
            self.conn.rollback()

    def verify_provider(self, tg_id, verified: bool, admin_tg_id: int | None = None, reason: str | None = None):
        """Updates verification status and portal account state when applicable."""
        query = """
        UPDATE providers
        SET is_verified = %s,
            account_state = CASE
                WHEN COALESCE(auth_channel, 'telegram') = 'portal' THEN %s
                ELSE COALESCE(account_state, 'approved')
            END,
            phone_verified = CASE
                WHEN COALESCE(auth_channel, 'telegram') = 'portal' AND %s THEN TRUE
                WHEN COALESCE(auth_channel, 'telegram') = 'portal' AND NOT %s THEN FALSE
                ELSE phone_verified
            END,
            approved_by_admin = CASE
                WHEN COALESCE(auth_channel, 'telegram') = 'portal' AND %s THEN %s
                ELSE approved_by_admin
            END,
            approved_at = CASE
                WHEN COALESCE(auth_channel, 'telegram') = 'portal' AND %s THEN NOW()
                ELSE approved_at
            END,
            rejection_reason = CASE
                WHEN COALESCE(auth_channel, 'telegram') = 'portal' AND %s THEN NULL
                WHEN COALESCE(auth_channel, 'telegram') = 'portal' THEN %s
                ELSE rejection_reason
            END,
            verification_code_used_at = CASE
                WHEN COALESCE(auth_channel, 'telegram') = 'portal' AND %s THEN NOW()
                ELSE verification_code_used_at
            END
        WHERE telegram_id = %s
        RETURNING id
        """
        next_state = "approved" if verified else "rejected"
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        verified,
                        next_state,
                        verified,
                        verified,
                        verified,
                        admin_tg_id,
                        verified,
                        verified,
                        reason,
                        verified,
                        tg_id,
                    ),
                )
                row = cur.fetchone()
                self.conn.commit()
                if row:
                    self.log_provider_verification_event(
                        provider_id=row["id"],
                        event_type="approved" if verified else "rejected",
                        payload={"reason": reason} if reason else {},
                        admin_telegram_id=admin_tg_id,
                    )
                    return True
                return False
        except Exception as e:
            logger.error(f"❌ Error updating verification status: {e}")
            self.conn.rollback()
            return False

    def log_provider_verification_event(
        self,
        provider_id: int,
        event_type: str,
        payload: dict | None = None,
        admin_telegram_id: int | None = None,
    ) -> bool:
        """Stores verification/security audit entries."""
        normalized = str(event_type or "").strip().lower()[:64]
        if not normalized:
            return False
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO provider_verification_events (provider_id, event_type, event_payload, admin_telegram_id)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (provider_id, normalized, Json(payload or {}), admin_telegram_id),
                )
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ Error logging provider verification event: {e}")
            self.conn.rollback()
            return False

    def toggle_online_status(self, tg_id) -> bool:
        """Toggles the is_online status and returns the new state."""
        query = "UPDATE providers SET is_online = NOT is_online WHERE telegram_id = %s RETURNING is_online"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (tg_id,))
                result = cur.fetchone()
                self.conn.commit()
                return result["is_online"] if result else False
        except Exception as e:
            logger.error(f"❌ Error toggling online status: {e}")
            self.conn.rollback()
            return False

    def set_online_status(self, tg_id, is_online: bool):
        """Sets the is_online status explicitly."""
        query = "UPDATE providers SET is_online = %s WHERE telegram_id = %s"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (is_online, tg_id))
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ Error setting online status: {e}")
            self.conn.rollback()
            return False

    # ==================== SUBSCRIPTION METHODS ====================

    def deactivate_expired_subscriptions(self):
        """Deactivates providers whose subscription has expired."""
        query = """
        UPDATE providers
        SET is_active = FALSE
        WHERE expiry_date < NOW() AND is_active = TRUE
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                count = cur.rowcount
                self.conn.commit()
                if count > 0:
                    logger.info(f"⏰ Deactivated {count} expired subscriptions")
                return count
        except Exception as e:
            logger.error(f"❌ Error deactivating expired: {e}")
            self.conn.rollback()
            return 0

    def activate_free_trial(self, tg_id: int, days: int = 7) -> bool:
        """
        Activates one-time free trial for verified providers.
        Eligibility: verified, inactive, trial not used, and no prior successful payments.
        """
        query = """
        UPDATE providers
        SET is_active = TRUE,
            expiry_date = NOW() + (%s || ' days')::INTERVAL,
            subscription_tier = 'trial',
            trial_used = TRUE,
            trial_started_at = NOW(),
            trial_reminder_day2_sent = FALSE,
            trial_reminder_day5_sent = FALSE,
            trial_reminder_lastday_sent = FALSE,
            trial_expired_notified = FALSE,
            trial_winback_sent = FALSE
        WHERE telegram_id = %s
          AND is_verified = TRUE
          AND is_active = FALSE
          AND COALESCE(trial_used, FALSE) = FALSE
          AND NOT EXISTS (
              SELECT 1
              FROM payments p
              WHERE p.telegram_id = %s
                AND p.status = 'SUCCESS'
          )
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (days, tg_id, tg_id))
                self.conn.commit()
                ok = cur.rowcount > 0
                if ok:
                    logger.info(f"🎁 Activated {days}-day free trial for {tg_id}")
                return ok
        except Exception as e:
            logger.error(f"❌ Error activating free trial: {e}")
            self.conn.rollback()
            return False

    def get_trial_reminder_candidates(self):
        """Gets active trial providers for reminder checks."""
        query = """
        SELECT telegram_id, display_name, expiry_date,
               COALESCE(trial_reminder_day2_sent, FALSE) AS trial_reminder_day2_sent,
               COALESCE(trial_reminder_day5_sent, FALSE) AS trial_reminder_day5_sent,
               COALESCE(trial_reminder_lastday_sent, FALSE) AS trial_reminder_lastday_sent
        FROM providers
        WHERE is_active = TRUE
          AND is_verified = TRUE
          AND subscription_tier = 'trial'
          AND expiry_date IS NOT NULL
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                return cur.fetchall()
        except Exception as e:
            logger.error(f"❌ Error fetching trial reminder candidates: {e}")
            return []

    def mark_trial_reminder_sent(self, tg_id: int, reminder_type: str) -> bool:
        """Marks a trial reminder as sent. reminder_type: day2|day5|lastday."""
        if reminder_type == "day2":
            query = "UPDATE providers SET trial_reminder_day2_sent = TRUE WHERE telegram_id = %s"
        elif reminder_type == "day5":
            query = "UPDATE providers SET trial_reminder_day5_sent = TRUE WHERE telegram_id = %s"
        elif reminder_type == "lastday":
            query = "UPDATE providers SET trial_reminder_lastday_sent = TRUE WHERE telegram_id = %s"
        else:
            return False
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (tg_id,))
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ Error marking trial reminder sent: {e}")
            self.conn.rollback()
            return False

    def get_unnotified_expired_trials(self):
        """Gets expired trial providers who have not received trial-ended notification."""
        query = """
        SELECT telegram_id, display_name
        FROM providers
        WHERE subscription_tier = 'trial'
          AND is_active = FALSE
          AND expiry_date IS NOT NULL
          AND expiry_date <= NOW()
          AND COALESCE(trial_expired_notified, FALSE) = FALSE
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                return cur.fetchall()
        except Exception as e:
            logger.error(f"❌ Error fetching expired trial notifications: {e}")
            return []

    def mark_trial_expired_notified(self, tg_id: int) -> bool:
        """Marks that trial-expired notification has been sent."""
        query = "UPDATE providers SET trial_expired_notified = TRUE WHERE telegram_id = %s"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (tg_id,))
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ Error marking trial expired notified: {e}")
            self.conn.rollback()
            return False

    def get_trial_winback_candidates(self, hours_after_expiry: int = 24):
        """Gets expired trial providers eligible for post-expiry winback message."""
        query = """
        SELECT telegram_id, display_name
        FROM providers
        WHERE subscription_tier = 'trial'
          AND is_active = FALSE
          AND expiry_date IS NOT NULL
          AND expiry_date <= NOW() - (%s || ' hours')::INTERVAL
          AND COALESCE(trial_expired_notified, FALSE) = TRUE
          AND COALESCE(trial_winback_sent, FALSE) = FALSE
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (hours_after_expiry,))
                return cur.fetchall()
        except Exception as e:
            logger.error(f"❌ Error fetching trial winback candidates: {e}")
            return []

    def mark_trial_winback_sent(self, tg_id: int) -> bool:
        """Marks that trial winback message has been sent."""
        query = "UPDATE providers SET trial_winback_sent = TRUE WHERE telegram_id = %s"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (tg_id,))
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ Error marking trial winback sent: {e}")
            self.conn.rollback()
            return False

    def has_successful_payment_for_provider(self, tg_id: int) -> bool:
        """Checks if provider has any successful payment history."""
        query = """
        SELECT 1
        FROM payments
        WHERE telegram_id = %s
          AND status = 'SUCCESS'
        LIMIT 1
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (tg_id,))
                return cur.fetchone() is not None
        except Exception as e:
            logger.error(f"❌ Error checking provider payment history: {e}")
            return False

    def log_funnel_event(self, tg_id: int, event_name: str, payload: dict | None = None) -> bool:
        """Logs a conversion funnel event for analytics."""
        query = """
        INSERT INTO bot_funnel_events (telegram_id, event_name, event_payload)
        VALUES (%s, %s, %s)
        """
        event_payload = payload or {}
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (tg_id, event_name[:64], Json(event_payload)))
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ Error logging funnel event '{event_name}': {e}")
            self.conn.rollback()
            return False

    def log_payment(self, tg_id, amount, reference, status, package_days):
        """Logs a payment transaction."""
        query = """
        INSERT INTO payments (telegram_id, amount, mpesa_reference, status, package_days)
        VALUES (%s, %s, %s, %s, %s)
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (tg_id, amount, reference, status, package_days))
                self.conn.commit()
                logger.info(f"💰 Payment logged: {tg_id} - {amount} KES - {status}")
                return True
        except Exception as e:
            logger.error(f"❌ Error logging payment: {e}")
            self.conn.rollback()
            return False

    def get_payment_by_reference(self, tg_id: int, reference: str):
        """Returns a specific payment record for a provider by reference."""
        query = """
        SELECT amount, mpesa_reference, status, package_days, created_at
        FROM payments
        WHERE telegram_id = %s AND mpesa_reference = %s
        ORDER BY created_at DESC
        LIMIT 1
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (tg_id, reference))
                return cur.fetchone()
        except Exception as e:
            logger.error(f"❌ Error getting payment by reference: {e}")
            return None

    def get_latest_payment_for_provider(self, tg_id: int):
        """Returns latest payment record for a provider."""
        query = """
        SELECT amount, mpesa_reference, status, package_days, created_at
        FROM payments
        WHERE telegram_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (tg_id,))
                return cur.fetchone()
        except Exception as e:
            logger.error(f"❌ Error getting latest payment: {e}")
            return None

    # ==================== BLACKLIST METHODS ====================

    def check_blacklist(self, phone: str) -> dict:
        """Checks if a phone number is blacklisted."""
        # Normalize phone number
        phone_clean = phone.replace(" ", "").replace("-", "").replace("+", "")
        if phone_clean.startswith("0"):
            phone_clean = "254" + phone_clean[1:]
        
        query = "SELECT * FROM blacklist WHERE phone = %s OR phone = %s"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (phone, phone_clean))
                result = cur.fetchone()
                if result:
                    return {
                        "blacklisted": True,
                        "reason": result["reason"],
                        "date": result["created_at"]
                    }
                return {"blacklisted": False}
        except Exception as e:
            logger.error(f"❌ Error checking blacklist: {e}")
            return {"blacklisted": False, "error": str(e)}

    def add_to_blacklist(self, phone: str, reason: str, reported_by: int) -> bool:
        """Adds a phone number to the blacklist."""
        phone_clean = phone.replace(" ", "").replace("-", "").replace("+", "")
        query = """
        INSERT INTO blacklist (phone, reason, reported_by)
        VALUES (%s, %s, %s)
        ON CONFLICT (phone) DO UPDATE SET reason = %s
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (phone_clean, reason, reported_by, reason))
                self.conn.commit()
                logger.info(f"🚫 Added to blacklist: {phone_clean}")
                return True
        except Exception as e:
            logger.error(f"❌ Error adding to blacklist: {e}")
            self.conn.rollback()
            return False

    # ==================== SESSION SAFETY METHODS ====================

    def start_session(self, tg_id: int, duration_minutes: int) -> int:
        """Starts a safety session timer. Returns session ID."""
        expected_back = datetime.now() + timedelta(minutes=duration_minutes)
        query = """
        INSERT INTO sessions (telegram_id, expected_check_back)
        VALUES (%s, %s)
        RETURNING id
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (tg_id, expected_back))
                result = cur.fetchone()
                self.conn.commit()
                logger.info(f"⏱️ Session started for {tg_id}, check-back at {expected_back}")
                return result["id"] if result else 0
        except Exception as e:
            logger.error(f"❌ Error starting session: {e}")
            self.conn.rollback()
            return 0

    def end_session(self, tg_id: int) -> bool:
        """Ends the active session for a provider (check-in)."""
        query = "UPDATE sessions SET is_active = FALSE WHERE telegram_id = %s AND is_active = TRUE"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (tg_id,))
                self.conn.commit()
                logger.info(f"✅ Session ended for {tg_id}")
                return True
        except Exception as e:
            logger.error(f"❌ Error ending session: {e}")
            self.conn.rollback()
            return False

    def get_overdue_sessions(self):
        """Gets sessions that have passed their expected check-back time and haven't been alerted."""
        query = """
        SELECT s.*, p.display_name, p.phone
        FROM sessions s
        JOIN providers p ON s.telegram_id = p.telegram_id
        WHERE s.is_active = TRUE 
          AND s.expected_check_back < NOW()
          AND s.admin_alerted = FALSE
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                return cur.fetchall()
        except Exception as e:
            logger.error(f"❌ Error getting overdue sessions: {e}")
            return []

    def mark_session_alerted(self, session_id: int):
        """Marks a session as having alerted the admin."""
        query = "UPDATE sessions SET admin_alerted = TRUE WHERE id = %s"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (session_id,))
                self.conn.commit()
        except Exception as e:
            logger.error(f"❌ Error marking session alerted: {e}")
            self.conn.rollback()

    # ==================== STATS METHODS ====================

    def get_recruitment_stats(self):
        """Gets recruitment statistics for the partner dashboard."""
        stats = {
            "total_users": 0,
            "verified_users": 0,
            "active_users": 0,
            "online_now": 0,
            "city_breakdown": {},
            "total_revenue": 0,
            "total_leads": 0,
            "leads_last_7d": 0,
            "top_neighborhoods_by_leads": {},
        }
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as count FROM providers")
                result = cur.fetchone()
                stats["total_users"] = result["count"] if result else 0
                
                cur.execute("SELECT COUNT(*) as count FROM providers WHERE is_verified = TRUE")
                result = cur.fetchone()
                stats["verified_users"] = result["count"] if result else 0
                
                cur.execute("SELECT COUNT(*) as count FROM providers WHERE is_active = TRUE")
                result = cur.fetchone()
                stats["active_users"] = result["count"] if result else 0
                
                cur.execute("SELECT COUNT(*) as count FROM providers WHERE is_online = TRUE AND is_active = TRUE")
                result = cur.fetchone()
                stats["online_now"] = result["count"] if result else 0
                
                cur.execute("""
                    SELECT city, COUNT(*) as count 
                    FROM providers 
                    WHERE city IS NOT NULL 
                    GROUP BY city 
                    ORDER BY count DESC
                """)
                for row in cur.fetchall():
                    stats["city_breakdown"][row["city"]] = row["count"]
                
                cur.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE status = 'SUCCESS'")
                result = cur.fetchone()
                stats["total_revenue"] = result["total"] if result else 0

                cur.execute("SELECT COUNT(*) AS count FROM lead_analytics")
                result = cur.fetchone()
                stats["total_leads"] = result["count"] if result else 0

                cur.execute("""
                    SELECT COUNT(*) AS count
                    FROM lead_analytics
                    WHERE created_at >= NOW() - INTERVAL '7 days'
                """)
                result = cur.fetchone()
                stats["leads_last_7d"] = result["count"] if result else 0

                cur.execute("""
                    SELECT
                        COALESCE(p.neighborhood, p.city, 'Unknown') AS area,
                        COUNT(*) AS count
                    FROM lead_analytics la
                    JOIN providers p ON p.id = la.provider_id
                    GROUP BY area
                    ORDER BY count DESC
                    LIMIT 5
                """)
                for row in cur.fetchall():
                    stats["top_neighborhoods_by_leads"][row["area"]] = row["count"]
                    
            return stats
        except Exception as e:
            logger.error(f"❌ Error getting recruitment stats: {e}")
            return stats

    def get_all_provider_ids(self):
        """Gets all provider telegram IDs for broadcast messages."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT telegram_id FROM providers")
                return [row["telegram_id"] for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"❌ Error getting provider IDs: {e}")
            return []
    
    # ==================== ADMIN FUNCTIONS ====================

    def get_verification_queue(self, queue_filter: str = "all_pending", limit: int = 10, offset: int = 0):
        """
        Gets pending verification queue rows with optional filters:
        - all_pending
        - new_today
        - pending_2h
        - missing_fields
        """
        base_where = "is_verified = FALSE AND verification_photo_id IS NOT NULL"
        if queue_filter == "new_today":
            extra_where = "AND created_at::date = CURRENT_DATE"
        elif queue_filter == "pending_2h":
            extra_where = "AND created_at <= NOW() - INTERVAL '2 hours'"
        elif queue_filter == "missing_fields":
            extra_where = """
            AND (
                display_name IS NULL OR NULLIF(TRIM(display_name), '') IS NULL OR
                city IS NULL OR neighborhood IS NULL OR age IS NULL OR
                build IS NULL OR NULLIF(TRIM(COALESCE(bio, '')), '') IS NULL OR
                services IS NULL OR services = '[]'::jsonb OR
                profile_photos IS NULL OR profile_photos = '[]'::jsonb
            )
            """
        else:
            extra_where = ""

        query = f"""
        SELECT telegram_id, display_name, city, neighborhood, created_at, verification_photo_id,
               ROUND(EXTRACT(EPOCH FROM (NOW() - created_at)) / 60.0) AS pending_minutes,
               (
                    CASE WHEN display_name IS NULL OR NULLIF(TRIM(display_name), '') IS NULL THEN 1 ELSE 0 END +
                    CASE WHEN city IS NULL THEN 1 ELSE 0 END +
                    CASE WHEN neighborhood IS NULL THEN 1 ELSE 0 END +
                    CASE WHEN age IS NULL THEN 1 ELSE 0 END +
                    CASE WHEN build IS NULL THEN 1 ELSE 0 END +
                    CASE WHEN NULLIF(TRIM(COALESCE(bio, '')), '') IS NULL THEN 1 ELSE 0 END +
                    CASE WHEN services IS NULL OR services = '[]'::jsonb THEN 1 ELSE 0 END +
                    CASE WHEN profile_photos IS NULL OR profile_photos = '[]'::jsonb THEN 1 ELSE 0 END
               ) AS missing_fields_count
        FROM providers
        WHERE {base_where}
        {extra_where}
        ORDER BY created_at ASC
        LIMIT %s OFFSET %s
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (limit, offset))
                return cur.fetchall()
        except Exception as e:
            logger.error(f"❌ Error getting verification queue: {e}")
            return []

    def get_verification_queue_count(self, queue_filter: str = "all_pending") -> int:
        """Gets total count for a specific verification queue filter."""
        base_where = "is_verified = FALSE AND verification_photo_id IS NOT NULL"
        if queue_filter == "new_today":
            extra_where = "AND created_at::date = CURRENT_DATE"
        elif queue_filter == "pending_2h":
            extra_where = "AND created_at <= NOW() - INTERVAL '2 hours'"
        elif queue_filter == "missing_fields":
            extra_where = """
            AND (
                display_name IS NULL OR NULLIF(TRIM(display_name), '') IS NULL OR
                city IS NULL OR neighborhood IS NULL OR age IS NULL OR
                build IS NULL OR NULLIF(TRIM(COALESCE(bio, '')), '') IS NULL OR
                services IS NULL OR services = '[]'::jsonb OR
                profile_photos IS NULL OR profile_photos = '[]'::jsonb
            )
            """
        else:
            extra_where = ""

        query = f"SELECT COUNT(*) AS count FROM providers WHERE {base_where} {extra_where}"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                result = cur.fetchone()
                return result["count"] if result else 0
        except Exception as e:
            logger.error(f"❌ Error counting verification queue: {e}")
            return 0

    def get_verification_queue_counts(self) -> dict:
        """Gets counts for queue filters used in admin moderation view."""
        return {
            "all_pending": self.get_verification_queue_count("all_pending"),
            "new_today": self.get_verification_queue_count("new_today"),
            "pending_2h": self.get_verification_queue_count("pending_2h"),
            "missing_fields": self.get_verification_queue_count("missing_fields"),
        }

    def get_portal_pending_accounts(self, limit: int = 10, offset: int = 0):
        """Lists portal accounts waiting for admin approval."""
        query = """
        SELECT
            telegram_id,
            display_name,
            phone,
            city,
            neighborhood,
            created_at,
            updated_at,
            account_state,
            portal_onboarding_complete,
            phone_verified,
            ROUND(EXTRACT(EPOCH FROM (NOW() - COALESCE(updated_at, created_at))) / 60.0) AS pending_minutes
        FROM providers
        WHERE COALESCE(auth_channel, 'telegram') = 'portal'
          AND COALESCE(account_state, 'pending_review') = 'pending_review'
        ORDER BY COALESCE(updated_at, created_at) ASC
        LIMIT %s OFFSET %s
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (limit, offset))
                return cur.fetchall()
        except Exception as e:
            logger.error(f"❌ Error getting portal pending accounts: {e}")
            return []

    def get_portal_pending_count(self) -> int:
        """Returns total number of portal accounts pending review."""
        query = """
        SELECT COUNT(*) AS count
        FROM providers
        WHERE COALESCE(auth_channel, 'telegram') = 'portal'
          AND COALESCE(account_state, 'pending_review') = 'pending_review'
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                result = cur.fetchone()
                return result["count"] if result else 0
        except Exception as e:
            logger.error(f"❌ Error counting portal pending accounts: {e}")
            return 0
    
    def get_providers_by_status(self, status_type: str, limit: int = 10, offset: int = 0):
        """
        Gets providers filtered by status type.
        status_type: 'unverified', 'verified', 'active', 'inactive', 'all'
        Returns list of provider dicts with basic info.
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                if status_type == 'unverified':
                    cur.execute("""
                        SELECT telegram_id, display_name, city, is_verified, is_active, created_at
                        FROM providers 
                        WHERE is_verified = FALSE
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                    """, (limit, offset))
                elif status_type == 'verified':
                    cur.execute("""
                        SELECT telegram_id, display_name, city, is_verified, is_active, created_at
                        FROM providers 
                        WHERE is_verified = TRUE
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                    """, (limit, offset))
                elif status_type == 'active':
                    cur.execute("""
                        SELECT telegram_id, display_name, city, is_verified, is_active, created_at
                        FROM providers 
                        WHERE is_active = TRUE
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                    """, (limit, offset))
                elif status_type == 'inactive':
                    cur.execute("""
                        SELECT telegram_id, display_name, city, is_verified, is_active, created_at
                        FROM providers 
                        WHERE is_active = FALSE
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                    """, (limit, offset))
                else:  # 'all'
                    cur.execute("""
                        SELECT telegram_id, display_name, city, is_verified, is_active, created_at
                        FROM providers 
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                    """, (limit, offset))
                
                return cur.fetchall()
        except Exception as e:
            logger.error(f"❌ Error getting providers by status: {e}")
            return []
    
    def get_provider_count_by_status(self, status_type: str):
        """Gets total count of providers by status type."""
        try:
            with self.conn.cursor() as cur:
                if status_type == 'unverified':
                    cur.execute("SELECT COUNT(*) as count FROM providers WHERE is_verified = FALSE")
                elif status_type == 'verified':
                    cur.execute("SELECT COUNT(*) as count FROM providers WHERE is_verified = TRUE")
                elif status_type == 'active':
                    cur.execute("SELECT COUNT(*) as count FROM providers WHERE is_active = TRUE")
                elif status_type == 'inactive':
                    cur.execute("SELECT COUNT(*) as count FROM providers WHERE is_active = FALSE")
                else:
                    cur.execute("SELECT COUNT(*) as count FROM providers")
                
                result = cur.fetchone()
                return result["count"] if result else 0
        except Exception as e:
            logger.error(f"❌ Error getting provider count: {e}")
            return 0
    
    def set_provider_active_status(self, tg_id, is_active: bool):
        """Sets provider's is_active status (list/unlist from site)."""
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "UPDATE providers SET is_active = %s WHERE telegram_id = %s",
                    (is_active, tg_id)
                )
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ Error setting active status: {e}")
            return False

    # ==================== BOOST METHODS ====================

    def boost_provider(self, tg_id: int, hours: int = 12) -> bool:
        """Boosts a provider's visibility for X hours."""
        boost_until = datetime.now() + timedelta(hours=hours)
        query = "UPDATE providers SET boost_until = %s WHERE telegram_id = %s"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (boost_until, tg_id))
                self.conn.commit()
                logger.info(f"🚀 Provider {tg_id} boosted until {boost_until}")
                return True
        except Exception as e:
            logger.error(f"❌ Error boosting provider: {e}")
            self.conn.rollback()
            return False

    def is_boosted(self, tg_id: int) -> bool:
        """Checks if a provider currently has an active boost."""
        query = "SELECT boost_until FROM providers WHERE telegram_id = %s"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (tg_id,))
                result = cur.fetchone()
                if result and result.get("boost_until"):
                    return result["boost_until"] > datetime.now()
                return False
        except Exception as e:
            logger.error(f"❌ Error checking boost: {e}")
            return False

    # ==================== REFERRAL METHODS ====================

    def generate_referral_code(self, tg_id: int) -> str:
        """Generates and stores a unique referral code for a provider."""
        import random
        import string
        code = 'BB' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        query = "UPDATE providers SET referral_code = %s WHERE telegram_id = %s AND (referral_code IS NULL OR referral_code = '')"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (code, tg_id))
                if cur.rowcount == 0:
                    # Already has a code, fetch it
                    cur.execute("SELECT referral_code FROM providers WHERE telegram_id = %s", (tg_id,))
                    result = cur.fetchone()
                    self.conn.commit()
                    return result["referral_code"] if result else code
                self.conn.commit()
                return code
        except Exception as e:
            logger.error(f"❌ Error generating referral code: {e}")
            self.conn.rollback()
            return code

    def get_referrer_by_code(self, code: str):
        """Finds the provider who owns a referral code."""
        query = "SELECT telegram_id, display_name FROM providers WHERE referral_code = %s"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (code.upper(),))
                return cur.fetchone()
        except Exception as e:
            logger.error(f"❌ Error looking up referral code: {e}")
            return None

    def set_referred_by(self, tg_id: int, referrer_tg_id: int) -> bool:
        """Records who referred this provider."""
        query = "UPDATE providers SET referred_by = %s WHERE telegram_id = %s AND referred_by IS NULL"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (referrer_tg_id, tg_id))
                self.conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            logger.error(f"❌ Error setting referral: {e}")
            self.conn.rollback()
            return False

    def add_referral_credits(self, tg_id: int, credits: int) -> bool:
        """Adds referral credits (in KES) to a provider."""
        query = "UPDATE providers SET referral_credits = COALESCE(referral_credits, 0) + %s WHERE telegram_id = %s"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (credits, tg_id))
                self.conn.commit()
                logger.info(f"🎁 Added {credits} KES credit to provider {tg_id}")
                return True
        except Exception as e:
            logger.error(f"❌ Error adding referral credits: {e}")
            self.conn.rollback()
            return False

    def get_referral_stats(self, tg_id: int) -> dict:
        """Gets referral statistics for a provider."""
        stats = {"referral_code": None, "total_referred": 0, "credits": 0}
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT referral_code, referral_credits FROM providers WHERE telegram_id = %s", (tg_id,))
                result = cur.fetchone()
                if result:
                    stats["referral_code"] = result.get("referral_code")
                    stats["credits"] = result.get("referral_credits", 0) or 0
                
                cur.execute("SELECT COUNT(*) as count FROM providers WHERE referred_by = %s", (tg_id,))
                result = cur.fetchone()
                stats["total_referred"] = result["count"] if result else 0
            return stats
        except Exception as e:
            logger.error(f"❌ Error getting referral stats: {e}")
            return stats

    def use_referral_credits(self, tg_id: int, amount: int) -> bool:
        """Deducts referral credits. Returns False if insufficient."""
        query = """UPDATE providers 
                   SET referral_credits = referral_credits - %s 
                   WHERE telegram_id = %s AND referral_credits >= %s"""
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (amount, tg_id, amount))
                self.conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            logger.error(f"❌ Error using referral credits: {e}")
            self.conn.rollback()
            return False

    # ==================== PREMIUM VERIFICATION ====================

    def set_premium_verified(self, tg_id: int) -> bool:
        """Grants premium verification badge."""
        query = "UPDATE providers SET is_premium_verified = TRUE WHERE telegram_id = %s"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (tg_id,))
                self.conn.commit()
                logger.info(f"⭐ Premium verification granted to {tg_id}")
                return True
        except Exception as e:
            logger.error(f"❌ Error setting premium verified: {e}")
            self.conn.rollback()
            return False

    # ==================== SUBSCRIPTION TIER ====================

    def activate_subscription(self, tg_id, days: int):
        """Activates provider subscription for X days with tier name."""
        from config import TIERS
        expiry = datetime.now() + timedelta(days=days)
        tier_info = TIERS.get(days, {})
        tier_name = tier_info.get("name", "Bronze").lower()
        query = """UPDATE providers 
                   SET is_active = TRUE, expiry_date = %s, subscription_tier = %s,
                       trial_expired_notified = FALSE,
                       trial_winback_sent = FALSE
                   WHERE telegram_id = %s"""
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (expiry, tier_name, tg_id))
                self.conn.commit()
                logger.info(f"✅ Activated {tier_name} subscription for {tg_id} until {expiry}")
                return True
        except Exception as e:
            logger.error(f"❌ Error activating subscription: {e}")
            self.conn.rollback()
            return False

