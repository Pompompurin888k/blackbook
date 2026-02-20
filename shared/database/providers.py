import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from pathlib import Path
from .base import BaseRepository

logger = logging.getLogger(__name__)

class ProvidersRepository(BaseRepository):
    """Repository for providers operations."""

    def get_provider(self, tg_id):
            """Fetch a specific provider by Telegram ID with all profile fields."""
            query = "SELECT * FROM providers WHERE telegram_id = %s"
            with self.conn.cursor() as cur:
                cur.execute(query, (tg_id,))
                return cur.fetchone()

    def get_active_providers(self, city: Optional[str] = None, neighborhood: Optional[str] = None) -> List[Dict]:
            """
            Fetches verified and active providers with smart ordering.
            Filters by city and/or neighborhood for high performance.
            Includes is_online for Live badge display.
            Smart ordering: Boosted first, then by tier (platinum>gold>silver>bronze),
            online first within each tier, recently verified next, then alphabetical.
            """

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

    def get_online_count(self) -> int:
            """Gets count of providers currently online."""
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

    def get_all_provider_ids(self):
            """Gets all provider telegram IDs for broadcast messages."""
            try:
                with self.conn.cursor() as cur:
                    cur.execute("SELECT telegram_id FROM providers")
                    return [row["telegram_id"] for row in cur.fetchall()]
            except Exception as e:
                logger.error(f"❌ Error getting provider IDs: {e}")
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

