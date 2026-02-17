import os
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import logging
from pathlib import Path

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
        self._run_startup_migrations()
    
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
                self.conn.autocommit = False
                logger.info("✅ Web app connected to database.")
                return
            except psycopg2.OperationalError:
                logger.info("⏳ Database is booting up... retrying in 2 seconds.")
                time.sleep(2)

    def _ensure_connection(self):
        """Checks if the database connection is alive and reconnects if needed."""
        if self.conn is None or self.conn.closed:
            logger.warning("⚠️ Database connection missing/closed. Reconnecting...")
            self._connect()
            return

        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
        except psycopg2.Error:
            # Recover from aborted transactions and stale connections.
            try:
                self.conn.rollback()
                with self.conn.cursor() as cur:
                    cur.execute("SELECT 1")
            except psycopg2.Error:
                logger.warning("⚠️ Database connection unhealthy. Reconnecting...")
                self._connect()

    def _run_startup_migrations(self):
        """Runs idempotent SQL migrations so deploys stay schema-compatible."""
        self._ensure_connection()
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
    
    def get_active_providers(self, city: Optional[str] = None, neighborhood: Optional[str] = None) -> List[Dict]:
        """
        Fetches verified and active providers with smart ordering.
        Filters by city and/or neighborhood for high performance.
        Includes is_online for Live badge display.
        Smart ordering: Boosted first, then by tier (platinum>gold>silver>bronze),
        online first within each tier, recently verified next, then alphabetical.
        """
        self._ensure_connection()
        
        # Common SELECT columns (includes tier/boost/premium fields)
        cols = """id, telegram_id, telegram_username, display_name, city, neighborhood, is_online,
                  age, height_cm, weight_kg, build, services, bio, created_at, profile_photos,
                  subscription_tier, boost_until, is_premium_verified"""
        
        # Smart ordering: boosted > tier priority > online > new > alphabetical
        order = """
            CASE WHEN boost_until > NOW() THEN 0 ELSE 1 END,
            CASE subscription_tier
                WHEN 'platinum' THEN 0
                WHEN 'gold' THEN 1
                WHEN 'silver' THEN 2
                ELSE 3
            END,
            is_online DESC,
            CASE WHEN created_at > NOW() - INTERVAL '30 days' THEN 0 ELSE 1 END,
            display_name"""
        
        try:
            with self.conn.cursor() as cur:
                if city and city.lower() != "all" and neighborhood:
                    cur.execute(f"""
                        SELECT {cols}
                        FROM providers
                        WHERE is_verified = TRUE AND is_active = TRUE 
                              AND city = %s AND neighborhood = %s
                        ORDER BY {order}
                    """, (city, neighborhood))
                elif city and city.lower() != "all":
                    cur.execute(f"""
                        SELECT {cols}
                        FROM providers
                        WHERE is_verified = TRUE AND is_active = TRUE AND city = %s
                        ORDER BY {order}
                    """, (city,))
                else:
                    cur.execute(f"""
                        SELECT {cols}
                        FROM providers
                        WHERE is_verified = TRUE AND is_active = TRUE
                        ORDER BY {order}
                    """)
                return cur.fetchall()
        except Exception as e:
            logger.error(f"❌ Error fetching providers: {e}")
            self._connect()
            return []

    def get_public_active_providers(self, city: Optional[str] = None, neighborhood: Optional[str] = None) -> List[Dict]:
        """
        Public provider listing payload for API consumers.
        Excludes sensitive fields like telegram_id and phone.
        """
        self._ensure_connection()

        cols = """id, display_name, city, neighborhood, is_online,
                  age, height_cm, weight_kg, build, services, bio, created_at, profile_photos,
                  subscription_tier, boost_until, is_premium_verified"""

        order = """
            CASE WHEN boost_until > NOW() THEN 0 ELSE 1 END,
            CASE subscription_tier
                WHEN 'platinum' THEN 0
                WHEN 'gold' THEN 1
                WHEN 'silver' THEN 2
                ELSE 3
            END,
            is_online DESC,
            CASE WHEN created_at > NOW() - INTERVAL '30 days' THEN 0 ELSE 1 END,
            display_name"""

        try:
            with self.conn.cursor() as cur:
                if city and city.lower() != "all" and neighborhood:
                    cur.execute(f"""
                        SELECT {cols}
                        FROM providers
                        WHERE is_verified = TRUE AND is_active = TRUE
                              AND city = %s AND neighborhood = %s
                        ORDER BY {order}
                    """, (city, neighborhood))
                elif city and city.lower() != "all":
                    cur.execute(f"""
                        SELECT {cols}
                        FROM providers
                        WHERE is_verified = TRUE AND is_active = TRUE AND city = %s
                        ORDER BY {order}
                    """, (city,))
                else:
                    cur.execute(f"""
                        SELECT {cols}
                        FROM providers
                        WHERE is_verified = TRUE AND is_active = TRUE
                        ORDER BY {order}
                    """)
                return cur.fetchall()
        except Exception as e:
            logger.error(f"❌ Error fetching public providers: {e}")
            self._connect()
            return []
    
    def get_city_counts(self) -> Dict[str, int]:
        """Gets count of active providers per city."""
        self._ensure_connection()
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
            try:
                self.conn.rollback()
            except Exception:
                pass
            return {}
    
    def get_total_verified_count(self) -> int:
        """Gets total count of verified active providers."""
        self._ensure_connection()
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM providers
                    WHERE is_verified = TRUE AND is_active = TRUE
                """)
                result = cur.fetchone()
                return result["count"] if result else 0
        except Exception as e:
            logger.error(f"❌ Error getting total verified count: {e}")
            try:
                self.conn.rollback()
            except Exception:
                pass
            return 0

    def healthcheck(self) -> bool:
        """Returns True when DB connection can answer a trivial query."""
        try:
            self._ensure_connection()
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
                row = cur.fetchone()
                return bool(row)
        except Exception as e:
            logger.error(f"❌ DB healthcheck failed: {e}")
            try:
                self.conn.rollback()
            except Exception:
                pass
            return False
    
    def get_online_count(self) -> int:
        """Gets count of providers currently online."""
        self._ensure_connection()
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM providers
                    WHERE is_verified = TRUE AND is_active = TRUE AND is_online = TRUE
                """)
                result = cur.fetchone()
                return result["count"] if result else 0
        except Exception as e:
            logger.error(f"❌ Error getting online count: {e}")
            try:
                self.conn.rollback()
            except Exception:
                pass
            return 0

    def get_premium_count(self) -> int:
        """Gets count of providers with Gold/Platinum tier or boosted."""
        self._ensure_connection()
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM providers
                    WHERE is_verified = TRUE AND is_active = TRUE
                      AND (subscription_tier IN ('gold', 'platinum') OR boost_until > NOW())
                """)
                result = cur.fetchone()
                return result["count"] if result else 0
        except Exception as e:
            logger.error(f"❌ Error getting premium count: {e}")
            try:
                self.conn.rollback()
            except Exception:
                pass
            return 0

    def get_provider_by_id(self, provider_id: int) -> Optional[Dict]:
        """Gets a single provider by database ID."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT id, telegram_id, display_name, phone, city, neighborhood, is_online,
                           age, height_cm, weight_kg, build, services, bio, nearby_places,
                           availability_type, languages,
                           rate_30min, rate_1hr, rate_2hr, rate_3hr, rate_overnight,
                           created_at, profile_photos, telegram_username,
                           subscription_tier, boost_until, is_premium_verified
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
                    SELECT id, telegram_id, display_name, city, neighborhood, is_online, expiry_date,
                           age, height_cm, weight_kg, build, services, bio, nearby_places,
                           subscription_tier, referred_by, referral_credits, is_verified
                    FROM providers
                    WHERE telegram_id = %s
                """, (telegram_id,))
                return cur.fetchone()
        except Exception as e:
            logger.error(f"❌ Error getting provider by Telegram ID: {e}")
            return None
    
    def activate_subscription(self, tg_id: int, days: int) -> bool:
        """Activates provider subscription for X days with tier name."""
        expiry = datetime.now() + timedelta(days=days)
        # Map days to tier name
        tier_map = {3: "bronze", 7: "silver", 30: "gold", 90: "platinum"}
        tier_name = tier_map.get(days, "bronze")
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

    def log_analytics_event(self, event_name: str, event_payload: Optional[Dict] = None) -> bool:
        """Stores lightweight frontend funnel analytics events."""
        self._ensure_connection()
        payload = event_payload or {}
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS analytics_events (
                        id BIGSERIAL PRIMARY KEY,
                        event_name VARCHAR(100) NOT NULL,
                        event_payload JSONB,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                cur.execute(
                    """
                    INSERT INTO analytics_events (event_name, event_payload)
                    VALUES (%s, %s)
                    """,
                    (event_name[:100], Json(payload))
                )
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error logging analytics event: {e}")
            self.conn.rollback()
            return False

    def log_funnel_event(self, tg_id: int, event_name: str, payload: Optional[Dict] = None) -> bool:
        """Stores bot/business funnel events from web-side callbacks."""
        self._ensure_connection()
        event_payload = payload or {}
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS bot_funnel_events (
                        id BIGSERIAL PRIMARY KEY,
                        telegram_id BIGINT NOT NULL,
                        event_name VARCHAR(64) NOT NULL,
                        event_payload JSONB,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                cur.execute(
                    """
                    INSERT INTO bot_funnel_events (telegram_id, event_name, event_payload)
                    VALUES (%s, %s, %s)
                    """,
                    (tg_id, event_name[:64], Json(event_payload)),
                )
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error logging funnel event '{event_name}': {e}")
            self.conn.rollback()
            return False

    def boost_provider(self, tg_id: int, hours: int = 12) -> bool:
        """Boosts a provider's visibility for X hours (only if provider is active)."""
        boost_until = datetime.now() + timedelta(hours=hours)
        query = """
            UPDATE providers
            SET boost_until = %s
            WHERE telegram_id = %s AND is_active = TRUE
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (boost_until, tg_id))
                self.conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            logger.error(f"❌ Error boosting provider: {e}")
            self.conn.rollback()
            return False

    def extend_subscription(self, tg_id: int, days: int) -> bool:
        """Extends an existing subscription by X days (for referral rewards)."""
        query = """UPDATE providers 
                   SET expiry_date = CASE 
                       WHEN expiry_date > NOW() THEN expiry_date + INTERVAL '%s days'
                       ELSE NOW() + INTERVAL '%s days'
                   END,
                   is_active = TRUE
                   WHERE telegram_id = %s"""
        try:
            with self.conn.cursor() as cur:
                # Can't use %s for INTERVAL, use string formatting for days
                cur.execute(
                    """UPDATE providers 
                       SET expiry_date = CASE 
                           WHEN expiry_date > NOW() THEN expiry_date + (%s || ' days')::INTERVAL
                           ELSE NOW() + (%s || ' days')::INTERVAL
                       END,
                       is_active = TRUE
                       WHERE telegram_id = %s""",
                    (str(days), str(days), tg_id)
                )
                self.conn.commit()
                logger.info(f"📅 Extended subscription for {tg_id} by {days} days")
                return True
        except Exception as e:
            logger.error(f"❌ Error extending subscription: {e}")
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

    def has_successful_payment(self, reference: str) -> bool:
        """Checks whether a successful payment with this reference already exists."""
        if not reference:
            return False
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM payments
                    WHERE mpesa_reference = %s AND status = 'SUCCESS'
                    LIMIT 1
                    """,
                    (reference,),
                )
                return cur.fetchone() is not None
        except Exception as e:
            logger.error(f"❌ Error checking payment reference: {e}")
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

    def get_recommendations(self, city: str, exclude_id: int, limit: int = 4) -> List[Dict]:
        """
        Fetches smart recommendations based on similarity scoring:
        - Same neighborhood: +10 points
        - Same build type: +5 points
        - Matching services: +2 per service match
        - Recently verified (within 30 days): +3 points
        - Same city (baseline): +5 points
        Results are ordered by relevance score with randomization for equal scores.
        """
        try:
            with self.conn.cursor() as cur:
                # First get the source provider's details for comparison
                cur.execute("""
                    SELECT neighborhood, build, services
                    FROM providers
                    WHERE id = %s
                """, (exclude_id,))
                source = cur.fetchone()
                
                if not source:
                    # Fallback to simple random if source not found
                    cur.execute("""
                        SELECT id, telegram_id, display_name, city, neighborhood, is_online,
                               age, height_cm, weight_kg, build, services, bio, nearby_places,
                               profile_photos, subscription_tier, is_premium_verified
                        FROM providers
                        WHERE is_verified = TRUE AND is_active = TRUE 
                              AND city = %s AND id != %s
                        ORDER BY RANDOM()
                        LIMIT %s
                    """, (city, exclude_id, limit))
                    return cur.fetchall()
                
                source_neighborhood = source.get('neighborhood', '')
                source_build = source.get('build', '')
                source_services = source.get('services', [])
                
                # Smart recommendation query with scoring
                cur.execute("""
                    SELECT 
                        id, telegram_id, display_name, city, neighborhood, is_online,
                        age, height_cm, weight_kg, build, services, bio, nearby_places,
                        created_at, profile_photos, subscription_tier, is_premium_verified,
                        (
                            -- Same neighborhood bonus
                            CASE WHEN neighborhood = %s THEN 10 ELSE 0 END +
                            
                            -- Same city baseline
                            CASE WHEN city = %s THEN 5 ELSE 0 END +
                            
                            -- Same build bonus
                            CASE WHEN build = %s THEN 5 ELSE 0 END +
                            
                            -- Recently verified bonus (within 30 days)
                            CASE WHEN created_at > NOW() - INTERVAL '30 days' THEN 3 ELSE 0 END +
                            
                            -- Online providers priority
                            CASE WHEN is_online = TRUE THEN 2 ELSE 0 END
                            
                        ) as relevance_score
                    FROM providers
                    WHERE is_verified = TRUE 
                          AND is_active = TRUE 
                          AND id != %s
                          AND city = %s
                    ORDER BY 
                        relevance_score DESC,
                        RANDOM()
                    LIMIT %s
                """, (source_neighborhood, city, source_build, exclude_id, city, limit))
                
                return cur.fetchall()
        except Exception as e:
            logger.error(f"❌ Error getting smart recommendations: {e}")
            # Fallback to simple query on error
            try:
                with self.conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, telegram_id, display_name, city, neighborhood, is_online,
                               age, height_cm, weight_kg, build, services, bio, nearby_places,
                               profile_photos, subscription_tier, is_premium_verified
                        FROM providers
                        WHERE is_verified = TRUE AND is_active = TRUE 
                              AND city = %s AND id != %s
                        ORDER BY is_online DESC, RANDOM()
                        LIMIT %s
                    """, (city, exclude_id, limit))
                    return cur.fetchall()
            except:
                return []

    def seed_test_providers(self):
        """Seeds the database with test providers for development with realistic names."""
        # Realistic female names
        names = [
            "Brenda", "Crystal", "Diamond", "Ebony", "Faith", "Grace", "Heaven", 
            "Jasmine", "Kenya", "Luna", "Maya", "Naomi", "Olivia", "Pearl",
            "Quinn", "Rose", "Sasha", "Tiffany", "Venus", "Zara", "Amber",
            "Bella", "Chloe", "Destiny", "Eva", "Fiona", "Giselle", "Hope"
        ]
        
        neighborhoods_nairobi = ["Westlands", "Lower Kabete", "Kilimani", "Lavington", "Karen", "Roysambu"]
        
        try:
            with self.conn.cursor() as cur:
                # First, delete all existing test providers (telegram_id >= 2000)
                cur.execute("DELETE FROM providers WHERE telegram_id >= 2000")
                deleted = cur.rowcount
                logger.info(f"🗑️ Deleted {deleted} old test providers")
                
                base_id = 2000
                count = 0
                name_index = 0
                
                # Nairobi Seeding: 4 per neighborhood
                for hood in neighborhoods_nairobi:
                    for i in range(1, 5): # 1 to 4
                        bg_id = base_id + count
                        name = names[name_index % len(names)]
                        name_index += 1
                        
                        cur.execute("""
                            INSERT INTO providers (
                                telegram_id, display_name, city, neighborhood, 
                                age, height_cm, weight_kg, build, services, bio, nearby_places, phone,
                                is_active, is_verified, is_online
                            ) VALUES (
                                %s, %s, 'Nairobi', %s, 
                                %s, %s, %s, %s, %s, %s, 'City Landmark', '254700000000',
                                TRUE, TRUE, %s
                            )
                        """, (
                            bg_id, name, hood, 
                            21 + (i * 2), # Age: 23, 25, 27, 29
                            160 + (i * 3), # Height: 163, 166, 169, 172
                            50 + (i * 2), # Weight: 52, 54, 56, 58
                            ["Slim", "Athletic", "Curvy", "Petite"][i % 4], # Vary build
                            '["GFE", "Massage"]', # JSON string
                            f"Sophisticated companion in {hood}. Discreet and professional.",
                            i % 2 == 0 # Alternate online status
                        ))
                        count += 1
                
                self.conn.commit()
                logger.info(f"✅ Database seeded with {count} new Nairobi providers with realistic names.")
        except Exception as e:
            logger.error(f"❌ Error seeding database: {e}")
            self.conn.rollback()

