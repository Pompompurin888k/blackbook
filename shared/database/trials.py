import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from pathlib import Path
from .base import BaseRepository

logger = logging.getLogger(__name__)

class TrialsRepository(BaseRepository):
    """Repository for trials operations."""

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

