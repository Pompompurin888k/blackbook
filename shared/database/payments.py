import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from pathlib import Path
from .base import BaseRepository

logger = logging.getLogger(__name__)

class PaymentsRepository(BaseRepository):
    """Repository for payments operations."""

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

    def create_referral_reward(self, referrer_id: int, invitee_id: int, amount_paid: int, reward_credit: int, reward_days: int) -> Optional[int]:
            """Creates a pending referral reward record and returns its ID."""
            query = """
            INSERT INTO referral_rewards (referrer_tg_id, invitee_tg_id, amount_paid, reward_credit, reward_days)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """
            try:
                with self.conn.cursor() as cur:
                    cur.execute(query, (referrer_id, invitee_id, amount_paid, reward_credit, reward_days))
                    result = cur.fetchone()
                    self.conn.commit()
                    return result["id"] if result else None
            except Exception as e:
                logger.error(f"❌ Error creating referral reward: {e}")
                self.conn.rollback()
                return None

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

    def get_referral_reward(self, reward_id: int) -> Optional[dict]:
            """Gets a specific referral reward by ID."""
            query = "SELECT * FROM referral_rewards WHERE id = %s"
            try:
                with self.conn.cursor() as cur:
                    cur.execute(query, (reward_id,))
                    return cur.fetchone()
            except Exception as e:
                logger.error(f"❌ Error getting referral reward {reward_id}: {e}")
                return None

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

    def mark_referral_reward_claimed(self, reward_id: int, choice: str) -> bool:
            """Marks a reward as claimed with the selected choice ('credit' or 'days')."""
            query = """
            UPDATE referral_rewards 
            SET is_claimed = TRUE, claimed_reward = %s, claimed_at = NOW() 
            WHERE id = %s AND is_claimed = FALSE
            """
            try:
                with self.conn.cursor() as cur:
                    cur.execute(query, (choice, reward_id))
                    self.conn.commit()
                    return cur.rowcount > 0
            except Exception as e:
                logger.error(f"❌ Error marking reward claimed: {e}")
                self.conn.rollback()
                return False

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

