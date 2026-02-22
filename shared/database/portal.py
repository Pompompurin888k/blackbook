import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from pathlib import Path
from .base import BaseRepository

logger = logging.getLogger(__name__)

class PortalRepository(BaseRepository):
    """Repository for portal operations."""

    def create_portal_provider_account(self, phone: str, password_hash: str, display_name: str) -> Optional[Dict]:
            """Creates a non-Telegram provider account for portal onboarding."""
            try:
                with self.conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1
                        FROM providers
                        WHERE phone = %s
                        LIMIT 1
                        """,
                        (phone,),
                    )
                    if cur.fetchone():
                        return None

                    cur.execute(
                        """
                        SELECT COALESCE(MIN(telegram_id), 0) AS min_id
                        FROM providers
                        WHERE telegram_id < 0
                        """
                    )
                    row = cur.fetchone() or {}
                    min_id = row.get("min_id") or 0
                    synthetic_tg_id = (int(min_id) - 1) if int(min_id) < 0 else -1
                    cur.execute(
                        """
                        INSERT INTO providers (
                            telegram_id,
                            display_name,
                            phone,
                            auth_channel,
                            portal_password_hash,
                            phone_verified,
                            account_state,
                            portal_onboarding_complete,
                            is_verified,
                            is_active
                        )
                        VALUES (%s, %s, %s, 'portal', %s, FALSE, 'pending_review', FALSE, FALSE, FALSE)
                        RETURNING id, telegram_id, display_name, phone, auth_channel
                        """,
                        (synthetic_tg_id, display_name, phone, password_hash),
                    )
                    created = cur.fetchone()
                    self.conn.commit()
                    return created
            except Exception as e:
                logger.error(f"❌ Error creating portal provider account: {e}")
                self.conn.rollback()
                return None

    def get_portal_provider_by_id(self, provider_id: int) -> Optional[Dict]:
            """Gets a provider account by internal provider ID for portal session."""
            try:
                with self.conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, telegram_id, display_name, phone, city, neighborhood,
                               is_verified, is_active, auth_channel, portal_password_hash,
                               phone_verified, phone_verify_code, phone_verify_code_created_at,
                               account_state, verification_code_hash, verification_code_expires_at,
                               verification_code_used_at, approved_by_admin, approved_at,
                               rejection_reason, login_failed_attempts, locked_until, last_login_attempt_at,
                               age, height_cm, weight_kg, build, services, bio, nearby_places,
                               availability_type, languages, profile_photos,
                               gender, sexual_orientation, nationality, county,
                               incalls_from, outcalls_from, video_url,
                               rate_30min, rate_1hr, rate_2hr, rate_3hr, rate_overnight,
                               created_at, subscription_tier, expiry_date,
                               boost_until, referral_credits,
                               trial_used, trial_started_at
                        FROM providers
                        WHERE id = %s
                        LIMIT 1
                        """,
                        (provider_id,),
                    )
                    return cur.fetchone()
            except Exception as e:
                logger.error(f"❌ Error getting portal provider by ID: {e}")
                return None

    def get_portal_provider_by_phone(self, phone: str) -> Optional[Dict]:
            """Gets a provider account by phone for portal login."""
            try:
                with self.conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, telegram_id, display_name, phone, city, neighborhood,
                               is_verified, is_active, auth_channel, portal_password_hash,
                               phone_verified, phone_verify_code, phone_verify_code_created_at,
                               account_state, verification_code_hash, verification_code_expires_at,
                               verification_code_used_at, approved_by_admin, approved_at,
                               rejection_reason, login_failed_attempts, locked_until, last_login_attempt_at,
                               portal_onboarding_complete, verification_photo_id,
                               age, height_cm, weight_kg, build, services, bio, nearby_places,
                               availability_type, languages, profile_photos,
                               gender, sexual_orientation, nationality, county,
                               incalls_from, outcalls_from, video_url,
                               rate_30min, rate_1hr, rate_2hr, rate_3hr, rate_overnight,
                               created_at, subscription_tier, expiry_date,
                               boost_until, referral_credits,
                               trial_used, trial_started_at
                        FROM providers
                        WHERE phone = %s AND COALESCE(auth_channel, 'telegram') = 'portal'
                        ORDER BY id DESC
                        LIMIT 1
                        """,
                        (phone,),
                    )
                    return cur.fetchone()
            except Exception as e:
                logger.error(f"❌ Error getting portal provider by phone: {e}")
                return None

    def register_portal_login_failure(self, provider_id: int, max_attempts: int, lock_minutes: int) -> Optional[Dict]:
            """Increments failed login attempts and applies lockout when threshold is reached."""
            try:
                with self.conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE providers
                        SET login_failed_attempts = COALESCE(login_failed_attempts, 0) + 1,
                            last_login_attempt_at = NOW(),
                            locked_until = CASE
                                WHEN COALESCE(login_failed_attempts, 0) + 1 >= %s
                                    THEN NOW() + (%s || ' minutes')::INTERVAL
                                ELSE locked_until
                            END
                        WHERE id = %s
                        RETURNING login_failed_attempts, locked_until
                        """,
                        (int(max_attempts), str(max(1, int(lock_minutes))), provider_id),
                    )
                    row = cur.fetchone()
                    self.conn.commit()
                    return row
            except Exception as e:
                logger.error(f"❌ Error tracking failed portal login: {e}")
                self.conn.rollback()
                return None

    def reset_portal_login_failures(self, provider_id: int) -> bool:
            """Clears failed login counters on successful authentication."""
            try:
                with self.conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE providers
                        SET login_failed_attempts = 0,
                            locked_until = NULL,
                            last_login_attempt_at = NOW()
                        WHERE id = %s
                        """,
                        (provider_id,),
                    )
                    self.conn.commit()
                    return cur.rowcount > 0
            except Exception as e:
                logger.error(f"❌ Error resetting portal login failures: {e}")
                self.conn.rollback()
                return False

    def update_portal_provider_profile(self, provider_id: int, data: Dict) -> bool:
            """Updates editable provider profile fields from portal onboarding."""
            allowed_fields = {
                "display_name",
                "city",
                "neighborhood",
                "age",
                "height_cm",
                "weight_kg",
                "build",
                "services",
                "bio",
                "nearby_places",
                "availability_type",
                "languages",
                "profile_photos",
                "rate_30min",
                "rate_1hr",
                "rate_2hr",
                "rate_3hr",
                "rate_overnight",
                "gender",
                "sexual_orientation",
                "nationality",
                "county",
                "incalls_from",
                "outcalls_from",
                "video_url",
                "verification_photo_id",
                "portal_onboarding_complete",
                "phone_verify_code",
                "phone_verify_code_created_at",
                "phone_verified",
                "account_state",
                "verification_code_hash",
                "verification_code_expires_at",
                "verification_code_used_at",
                "approved_by_admin",
                "approved_at",
                "rejection_reason",
                "login_failed_attempts",
                "locked_until",
                "last_login_attempt_at",
                "is_online",
            }
            sanitized = {k: v for k, v in data.items() if k in allowed_fields}
            if not sanitized:
                return False

            assignments = []
            values = []
            for key, value in sanitized.items():
                assignments.append(f"{key} = %s")
                if key in {"services", "languages", "profile_photos"} and isinstance(value, list):
                    values.append(Json(value))
                else:
                    values.append(value)
            values.append(provider_id)

            try:
                with self.conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE providers SET {', '.join(assignments)} WHERE id = %s",
                        tuple(values),
                    )
                    self.conn.commit()
                    return cur.rowcount > 0
            except Exception as e:
                logger.error(f"❌ Error updating portal profile: {e}")
                self.conn.rollback()
                return False

    def set_portal_phone_verification_code(
            self,
            provider_id: int,
            code: str,
            code_hash: str,
            ttl_minutes: int = 30,
            mark_pending: bool = True,
        ) -> bool:
            """Stores the latest manual phone verification code for WhatsApp confirmation."""
            try:
                with self.conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE providers
                        SET phone_verify_code = %s,
                            verification_code_hash = %s,
                            verification_code_expires_at = NOW() + (%s || ' minutes')::INTERVAL,
                            verification_code_used_at = NULL,
                            phone_verify_code_created_at = NOW()
                            ,
                            account_state = CASE
                                WHEN %s AND COALESCE(account_state, 'approved') != 'approved' THEN 'pending_review'
                                ELSE COALESCE(account_state, 'approved')
                            END
                        WHERE id = %s
                        """,
                        (code, code_hash, str(max(1, int(ttl_minutes))), bool(mark_pending), provider_id),
                    )
                    self.conn.commit()
                    return cur.rowcount > 0
            except Exception as e:
                logger.error(f"❌ Error setting phone verification code: {e}")
                self.conn.rollback()
                return False

