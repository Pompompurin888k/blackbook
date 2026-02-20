import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from pathlib import Path
from .base import BaseRepository

logger = logging.getLogger(__name__)

class VerificationRepository(BaseRepository):
    """Repository for verification operations."""

    def log_provider_verification_event(
            self,
            provider_id: int,
            event_type: str,
            payload: Optional[Dict] = None,
            admin_telegram_id: Optional[int] = None,
        ) -> bool:
            """Writes provider verification/security events for auditability."""
            normalized_event = str(event_type or "").strip().lower()[:64]
            if not normalized_event:
                return False
            event_payload = payload or {}
            try:
                with self.conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO provider_verification_events (
                            provider_id,
                            event_type,
                            event_payload,
                            admin_telegram_id
                        )
                        VALUES (%s, %s, %s, %s)
                        """,
                        (provider_id, normalized_event, Json(event_payload), admin_telegram_id),
                    )
                    self.conn.commit()
                    return True
            except Exception as e:
                logger.error(f"❌ Error logging provider verification event: {e}")
                self.conn.rollback()
                return False

    def count_provider_verification_events(
            self,
            provider_id: int,
            event_type: str,
            hours: int = 24,
        ) -> int:
            """Counts recent verification events for basic rate limiting."""
            normalized_event = str(event_type or "").strip().lower()[:64]
            if not normalized_event:
                return 0
            try:
                with self.conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COUNT(*) AS count
                        FROM provider_verification_events
                        WHERE provider_id = %s
                          AND event_type = %s
                          AND created_at >= NOW() - (%s || ' hours')::INTERVAL
                        """,
                        (provider_id, normalized_event, str(max(1, int(hours)))),
                    )
                    row = cur.fetchone()
                    return int(row["count"]) if row else 0
            except Exception as e:
                logger.error(f"❌ Error counting provider verification events: {e}")
                self.conn.rollback()
                return 0

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

