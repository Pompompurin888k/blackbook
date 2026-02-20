import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from pathlib import Path
from .base import BaseRepository

logger = logging.getLogger(__name__)

class SafetyRepository(BaseRepository):
    """Repository for safety operations."""

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

    def get_active_session(self, tg_id: int) -> Optional[Dict]:
            """Returns the most recent active safety session for a provider."""
            query = """
            SELECT id, telegram_id, expected_check_back, created_at
            FROM sessions
            WHERE telegram_id = %s AND is_active = TRUE
            ORDER BY created_at DESC
            LIMIT 1
            """
            try:
                with self.conn.cursor() as cur:
                    cur.execute(query, (tg_id,))
                    return cur.fetchone()
            except Exception as e:
                logger.error(f"❌ Error getting active session for {tg_id}: {e}")
                return None
