import os
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import logging

# Setup Logging so you can see what's happening in 'docker logs blackbook_bot'
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.host = os.getenv("DB_HOST", "localhost")  # Changed from "db" to "localhost" for host network mode
        self.database = os.getenv("DB_NAME", "blackbook_db")
        self.user = os.getenv("DB_USER", "bb_operator")
        self.password = os.getenv("DB_PASSWORD")
        self.port = os.getenv("DB_PORT", "8291")  # Changed from "5432" to "8291" (mapped port)
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        END $$;
        """
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(providers_query)
                cur.execute(payments_query)
                cur.execute(blacklist_query)
                cur.execute(sessions_query)
                cur.execute(add_columns)
                self.conn.commit()
                logger.info("🛠️ Database tables initialized.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize tables: {e}")

    # ==================== PROVIDER METHODS ====================
    
    def get_provider(self, tg_id):
        """Fetch a specific provider by Telegram ID with all profile fields."""
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
            
        # Build dynamic query
        set_clauses = []
        values = []
        
        for key, value in data.items():
            set_clauses.append(f"{key} = %s")
            values.append(value)
            
        values.append(tg_id) # For WHERE clause
        
        query = f"UPDATE providers SET {', '.join(set_clauses)} WHERE telegram_id = %s"
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, tuple(values))
                self.conn.commit()
                logger.info(f"✅ Updated profile for {tg_id}: {list(data.keys())}")
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

    def verify_provider(self, tg_id, verified: bool):
        """Updates the is_verified status for a provider."""
        query = "UPDATE providers SET is_verified = %s WHERE telegram_id = %s"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (verified, tg_id))
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ Error updating verification status: {e}")
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

    def activate_subscription(self, tg_id, days: int):
        """Activates provider subscription for X days. Sets is_active=TRUE and expiry_date."""
        expiry = datetime.now() + timedelta(days=days)
        query = "UPDATE providers SET is_active = TRUE, expiry_date = %s WHERE telegram_id = %s"
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (expiry, tg_id))
                self.conn.commit()
                logger.info(f"✅ Activated subscription for {tg_id} until {expiry}")
                return True
        except Exception as e:
            logger.error(f"❌ Error activating subscription: {e}")
            self.conn.rollback()
            return False

    def deactivate_expired_subscriptions(self):
        """Deactivates providers whose subscription has expired."""
        query = "UPDATE providers SET is_active = FALSE WHERE expiry_date < NOW() AND is_active = TRUE"
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
            "total_revenue": 0
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
