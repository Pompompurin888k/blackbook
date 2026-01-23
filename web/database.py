import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Database:
    """Database connection for the web frontend (includes write ops for payment callbacks)."""
    
    def __init__(self):
        self.host = os.getenv("DB_HOST", "db")
        self.database = os.getenv("DB_NAME", "blackbook_db")
        self.user = os.getenv("DB_USER", "bb_operator")
        self.password = os.getenv("DB_PASSWORD")
        self.port = os.getenv("DB_PORT", "5432")
        self.conn = None
        self._connect()
    
    def _connect(self):
        """Establishes database connection with retry logic."""
        import time
        while True:
            try:
                self.conn = psycopg2.connect(
                    host=self.host,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                    port=self.port,
                    cursor_factory=RealDictCursor
                )
                logger.info("✅ Web app connected to database.")
                return
            except psycopg2.OperationalError:
                logger.info("⏳ Database is booting up... retrying in 2 seconds.")
                time.sleep(2)
    
    def get_active_providers(self, city: Optional[str] = None, neighborhood: Optional[str] = None) -> List[Dict]:
        """
        Fetches verified and active providers.
        Filters by city and/or neighborhood for high performance.
        Includes is_online for Live badge display.
        """
        try:
            with self.conn.cursor() as cur:
                if city and city.lower() != "all" and neighborhood:
                    cur.execute("""
                        SELECT id, telegram_id, display_name, city, neighborhood, is_online
                        FROM providers
                        WHERE is_verified = TRUE AND is_active = TRUE 
                              AND city = %s AND neighborhood = %s
                        ORDER BY is_online DESC, display_name
                    """, (city, neighborhood))
                elif city and city.lower() != "all":
                    cur.execute("""
                        SELECT id, telegram_id, display_name, city, neighborhood, is_online
                        FROM providers
                        WHERE is_verified = TRUE AND is_active = TRUE AND city = %s
                        ORDER BY is_online DESC, display_name
                    """, (city,))
                else:
                    cur.execute("""
                        SELECT id, telegram_id, display_name, city, neighborhood, is_online
                        FROM providers
                        WHERE is_verified = TRUE AND is_active = TRUE
                        ORDER BY is_online DESC, city, display_name
                    """)
                return cur.fetchall()
        except Exception as e:
            logger.error(f"❌ Error fetching providers: {e}")
            self._connect()
            return []
    
    def get_city_counts(self) -> Dict[str, int]:
        """Gets count of active providers per city."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT city, COUNT(*) as count
                    FROM providers
                    WHERE is_verified = TRUE AND is_active = TRUE AND city IS NOT NULL
                    GROUP BY city
                    ORDER BY count DESC
                """)
                return {row["city"]: row["count"] for row in cur.fetchall()}
        except Exception as e:
            logger.error(f"❌ Error getting city counts: {e}")
            return {}

    def get_provider_by_id(self, provider_id: int) -> Optional[Dict]:
        """Gets a single provider by database ID."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT id, telegram_id, display_name, city, neighborhood, is_online
                    FROM providers
                    WHERE id = %s AND is_verified = TRUE AND is_active = TRUE
                """, (provider_id,))
                return cur.fetchone()
        except Exception as e:
            logger.error(f"❌ Error getting provider by ID: {e}")
            return None
    
    def get_provider_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        """Gets a single provider by Telegram ID."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT id, telegram_id, display_name, city, neighborhood, is_online, expiry_date
                    FROM providers
                    WHERE telegram_id = %s
                """, (telegram_id,))
                return cur.fetchone()
        except Exception as e:
            logger.error(f"❌ Error getting provider by Telegram ID: {e}")
            return None
    
    def activate_subscription(self, tg_id: int, days: int) -> bool:
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

    def log_payment(self, tg_id: int, amount: int, reference: str, status: str, package_days: int) -> bool:
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
