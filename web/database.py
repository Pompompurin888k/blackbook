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
        Fetches verified and active providers with smart ordering.
        Filters by city and/or neighborhood for high performance.
        Includes is_online for Live badge display.
        Smart ordering: Online first, recently verified next, then alphabetical.
        """
        try:
            with self.conn.cursor() as cur:
                if city and city.lower() != "all" and neighborhood:
                    cur.execute("""
                        SELECT id, telegram_id, display_name, city, neighborhood, is_online, phone,
                               age, height_cm, weight_kg, build, services, bio, created_at
                        FROM providers
                        WHERE is_verified = TRUE AND is_active = TRUE 
                              AND city = %s AND neighborhood = %s
                        ORDER BY 
                            is_online DESC,
                            CASE WHEN created_at > NOW() - INTERVAL '30 days' THEN 0 ELSE 1 END,
                            display_name
                    """, (city, neighborhood))
                elif city and city.lower() != "all":
                    cur.execute("""
                        SELECT id, telegram_id, display_name, city, neighborhood, is_online, phone,
                               age, height_cm, weight_kg, build, services, bio, created_at
                        FROM providers
                        WHERE is_verified = TRUE AND is_active = TRUE AND city = %s
                        ORDER BY 
                            is_online DESC,
                            CASE WHEN created_at > NOW() - INTERVAL '30 days' THEN 0 ELSE 1 END,
                            neighborhood,
                            display_name
                    """, (city,))
                else:
                    cur.execute("""
                        SELECT id, telegram_id, display_name, city, neighborhood, is_online, phone,
                               age, height_cm, weight_kg, build, services, bio, created_at
                        FROM providers
                        WHERE is_verified = TRUE AND is_active = TRUE
                        ORDER BY 
                            is_online DESC,
                            CASE WHEN created_at > NOW() - INTERVAL '30 days' THEN 0 ELSE 1 END,
                            city,
                            display_name
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
                    SELECT id, telegram_id, display_name, city, neighborhood, is_online,
                           age, height_cm, weight_kg, build, services, bio, nearby_places
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
                           age, height_cm, weight_kg, build, services, bio, nearby_places
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
                        SELECT id, telegram_id, display_name, city, neighborhood, is_online, phone,
                               age, height_cm, weight_kg, build, services, bio, nearby_places
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
                        id, telegram_id, display_name, city, neighborhood, is_online, phone,
                        age, height_cm, weight_kg, build, services, bio, nearby_places,
                        created_at,
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
                        SELECT id, telegram_id, display_name, city, neighborhood, is_online, phone,
                               age, height_cm, weight_kg, build, services, bio, nearby_places
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
