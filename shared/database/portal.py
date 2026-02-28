import logging
from typing import Dict, Optional

from psycopg2.extras import Json

from .base import BaseRepository

logger = logging.getLogger(__name__)


class PortalRepository(BaseRepository):
    """Repository for portal operations."""

    def create_portal_provider_account(
        self,
        phone: Optional[str],
        email: str,
        username: str,
        password_hash: str,
        display_name: str,
    ) -> Optional[Dict]:
        """Creates a non-Telegram provider account for portal onboarding."""
        normalized_phone = (phone or "").strip()
        normalized_email = (email or "").strip().lower()
        normalized_username = (username or "").strip().lower().lstrip("@")
        if not normalized_email or not normalized_username:
            return None

        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM providers
                    WHERE LOWER(COALESCE(email, '')) = %s
                       OR (
                            COALESCE(auth_channel, 'telegram') = 'portal'
                            AND LOWER(COALESCE(telegram_username, '')) = %s
                          )
                       OR (%s <> '' AND phone = %s)
                    LIMIT 1
                    """,
                    (normalized_email, normalized_username, normalized_phone, normalized_phone),
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
                        telegram_username,
                        display_name,
                        phone,
                        email,
                        auth_channel,
                        portal_password_hash,
                        email_verified,
                        phone_verified,
                        account_state,
                        portal_onboarding_complete,
                        is_verified,
                        is_active
                    )
                    VALUES (%s, %s, %s, %s, %s, 'portal', %s, FALSE, FALSE, 'pending_review', FALSE, FALSE, FALSE)
                    RETURNING id, telegram_id, telegram_username, display_name, phone, email, auth_channel
                    """,
                    (
                        synthetic_tg_id,
                        normalized_username,
                        display_name,
                        normalized_phone or None,
                        normalized_email,
                        password_hash,
                    ),
                )
                created = cur.fetchone()
                self.conn.commit()
                return created
        except Exception as e:
            logger.error(f"Error creating portal provider account: {e}")
            self.conn.rollback()
            return None

    def get_portal_provider_by_id(self, provider_id: int) -> Optional[Dict]:
        """Gets a provider account by internal provider ID for portal session."""
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, telegram_id, telegram_username, display_name, phone, email, city, neighborhood,
                           is_verified, is_active, auth_channel, portal_password_hash,
                           email_verified, email_verify_code_created_at,
                           password_reset_code_hash, password_reset_code_expires_at, password_reset_code_used_at,
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
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (provider_id,),
                )
                return cur.fetchone()
        except Exception as e:
            logger.error(f"Error getting portal provider by ID: {e}")
            return None

    def get_portal_provider_by_phone(self, phone: str) -> Optional[Dict]:
        """Gets a provider account by phone for portal login."""
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, telegram_id, telegram_username, display_name, phone, email, city, neighborhood,
                           is_verified, is_active, auth_channel, portal_password_hash,
                           email_verified, email_verify_code_created_at,
                           password_reset_code_hash, password_reset_code_expires_at, password_reset_code_used_at,
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
            logger.error(f"Error getting portal provider by phone: {e}")
            return None

    def get_portal_provider_by_email(self, email: str) -> Optional[Dict]:
        """Gets a portal provider account by email for authentication."""
        normalized_email = (email or "").strip().lower()
        if not normalized_email:
            return None
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, telegram_id, telegram_username, display_name, phone, email, city, neighborhood,
                           is_verified, is_active, auth_channel, portal_password_hash,
                           email_verified, email_verify_code_created_at,
                           password_reset_code_hash, password_reset_code_expires_at, password_reset_code_used_at,
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
                    WHERE LOWER(COALESCE(email, '')) = %s
                      AND COALESCE(auth_channel, 'telegram') = 'portal'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (normalized_email,),
                )
                return cur.fetchone()
        except Exception as e:
            logger.error(f"Error getting portal provider by email: {e}")
            return None

    def get_portal_provider_by_username(self, username: str) -> Optional[Dict]:
        """Gets a portal provider account by username for authentication."""
        normalized_username = (username or "").strip().lower().lstrip("@")
        if not normalized_username:
            return None
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, telegram_id, telegram_username, display_name, phone, email, city, neighborhood,
                           is_verified, is_active, auth_channel, portal_password_hash,
                           email_verified, email_verify_code_created_at,
                           password_reset_code_hash, password_reset_code_expires_at, password_reset_code_used_at,
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
                    WHERE LOWER(COALESCE(telegram_username, '')) = %s
                      AND COALESCE(auth_channel, 'telegram') = 'portal'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (normalized_username,),
                )
                return cur.fetchone()
        except Exception as e:
            logger.error(f"Error getting portal provider by username: {e}")
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
            logger.error(f"Error tracking failed portal login: {e}")
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
            logger.error(f"Error resetting portal login failures: {e}")
            self.conn.rollback()
            return False

    def update_portal_provider_profile(self, provider_id: int, data: Dict) -> bool:
        """Updates editable provider profile fields from portal onboarding."""
        allowed_fields = {
            "display_name",
            "phone",
            "email",
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
            "email_verified",
            "email_verify_code_created_at",
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
            logger.error(f"Error updating portal profile: {e}")
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
        """Stores legacy manual phone verification code for WhatsApp confirmation."""
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE providers
                    SET phone_verify_code = %s,
                        verification_code_hash = %s,
                        verification_code_expires_at = NOW() + (%s || ' minutes')::INTERVAL,
                        verification_code_used_at = NULL,
                        phone_verify_code_created_at = NOW(),
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
            logger.error(f"Error setting phone verification code: {e}")
            self.conn.rollback()
            return False

    def set_portal_email_verification_code(
        self,
        provider_id: int,
        code_hash: str,
        ttl_minutes: int = 30,
        mark_pending: bool = True,
    ) -> bool:
        """Stores a hashed portal email verification code."""
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE providers
                    SET verification_code_hash = %s,
                        verification_code_expires_at = NOW() + (%s || ' minutes')::INTERVAL,
                        verification_code_used_at = NULL,
                        email_verify_code_created_at = NOW(),
                        account_state = CASE
                            WHEN %s AND COALESCE(account_state, 'approved') != 'approved' THEN 'pending_review'
                            ELSE COALESCE(account_state, 'approved')
                        END
                    WHERE id = %s
                    """,
                    (code_hash, str(max(1, int(ttl_minutes))), bool(mark_pending), provider_id),
                )
                self.conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Error setting email verification code: {e}")
            self.conn.rollback()
            return False

    def mark_portal_email_verified(self, provider_id: int) -> bool:
        """Marks portal email verification as complete and unlocks account."""
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE providers
                    SET email_verified = TRUE,
                        account_state = 'approved',
                        verification_code_hash = NULL,
                        verification_code_expires_at = NULL,
                        verification_code_used_at = NOW(),
                        rejection_reason = NULL,
                        approved_at = COALESCE(approved_at, NOW())
                    WHERE id = %s
                    """,
                    (provider_id,),
                )
                self.conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Error marking portal email verified: {e}")
            self.conn.rollback()
            return False

    def set_portal_password_reset_code(
        self,
        provider_id: int,
        code_hash: str,
        ttl_minutes: int = 30,
    ) -> bool:
        """Stores a hashed password-reset code for portal authentication."""
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE providers
                    SET password_reset_code_hash = %s,
                        password_reset_code_expires_at = NOW() + (%s || ' minutes')::INTERVAL,
                        password_reset_code_used_at = NULL
                    WHERE id = %s
                    """,
                    (code_hash, str(max(1, int(ttl_minutes))), provider_id),
                )
                self.conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Error setting portal password reset code: {e}")
            self.conn.rollback()
            return False

    def reset_portal_password(self, provider_id: int, password_hash: str) -> bool:
        """Updates portal password and invalidates any active password-reset code."""
        if not password_hash:
            return False
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE providers
                    SET portal_password_hash = %s,
                        password_reset_code_hash = NULL,
                        password_reset_code_expires_at = NULL,
                        password_reset_code_used_at = NOW(),
                        login_failed_attempts = 0,
                        locked_until = NULL,
                        last_login_attempt_at = NOW()
                    WHERE id = %s
                    """,
                    (password_hash, provider_id),
                )
                self.conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Error resetting portal password: {e}")
            self.conn.rollback()
            return False
