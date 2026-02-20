import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from pathlib import Path
from .base import BaseRepository

logger = logging.getLogger(__name__)

class AnalyticsRepository(BaseRepository):
    """Repository for analytics operations."""

    def log_analytics_event(self, event_name: str, event_payload: Optional[Dict] = None) -> bool:
            """Stores lightweight frontend funnel analytics events."""
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

    def log_lead_analytics(
            self,
            provider_id: int,
            client_ip: str,
            device_type: str,
            contact_method: str,
            is_stealth: bool = False,
        ) -> bool:
            """Logs provider lead click-through events for contact actions."""
            method = (contact_method or "").strip().lower()
            if method not in {"whatsapp", "call"}:
                method = "whatsapp"
            try:
                with self.conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO lead_analytics (
                            provider_id,
                            client_ip,
                            device_type,
                            contact_method,
                            is_stealth
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            provider_id,
                            (client_ip or "")[:100],
                            (device_type or "unknown")[:20],
                            method,
                            bool(is_stealth),
                        ),
                    )
                    self.conn.commit()
                    return True
            except Exception as e:
                logger.error(f"Error logging lead analytics: {e}")
                self.conn.rollback()
                return False

    def get_recruitment_stats(self):
            """Gets recruitment statistics for the partner dashboard."""
            stats = {
                "total_users": 0,
                "verified_users": 0,
                "active_users": 0,
                "online_now": 0,
                "city_breakdown": {},
                "total_revenue": 0,
                "total_leads": 0,
                "leads_last_7d": 0,
                "top_neighborhoods_by_leads": {},
            }
            try:
                with self.conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) as count FROM providers")
                    result = cur.fetchone()
                    stats["total_users"] = result["count"] if result else 0

                    cur.execute("SELECT COUNT(*) as count FROM providers WHERE is_verified = TRUE")
                    result = cur.fetchone()
                    stats["verified_users"] = result["count"] if result else 0

                    cur.execute("SELECT COUNT(*) as count FROM providers WHERE is_active = TRUE")
                    result = cur.fetchone()
                    stats["active_users"] = result["count"] if result else 0

                    cur.execute("SELECT COUNT(*) as count FROM providers WHERE is_online = TRUE AND is_active = TRUE")
                    result = cur.fetchone()
                    stats["online_now"] = result["count"] if result else 0

                    cur.execute("""
                        SELECT city, COUNT(*) as count 
                        FROM providers 
                        WHERE city IS NOT NULL 
                        GROUP BY city 
                        ORDER BY count DESC
                    """)
                    for row in cur.fetchall():
                        stats["city_breakdown"][row["city"]] = row["count"]

                    cur.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE status = 'SUCCESS'")
                    result = cur.fetchone()
                    stats["total_revenue"] = result["total"] if result else 0

                    cur.execute("SELECT COUNT(*) AS count FROM lead_analytics")
                    result = cur.fetchone()
                    stats["total_leads"] = result["count"] if result else 0

                    cur.execute("""
                        SELECT COUNT(*) AS count
                        FROM lead_analytics
                        WHERE created_at >= NOW() - INTERVAL '7 days'
                    """)
                    result = cur.fetchone()
                    stats["leads_last_7d"] = result["count"] if result else 0

                    cur.execute("""
                        SELECT
                            COALESCE(p.neighborhood, p.city, 'Unknown') AS area,
                            COUNT(*) AS count
                        FROM lead_analytics la
                        JOIN providers p ON p.id = la.provider_id
                        GROUP BY area
                        ORDER BY count DESC
                        LIMIT 5
                    """)
                    for row in cur.fetchall():
                        stats["top_neighborhoods_by_leads"][row["area"]] = row["count"]

                return stats
            except Exception as e:
                logger.error(f"❌ Error getting recruitment stats: {e}")
                return stats

