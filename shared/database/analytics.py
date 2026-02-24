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

    def get_provider_analytics_stats(self, provider_id: int) -> Dict:
        """Retrieves profile views and contact clicks for a specific provider."""
        stats = {
            "total_views": 0,
            "views_7d": 0,
            "total_clicks": 0,
            "clicks_7d": 0,
            "clicks_by_method": {},
            "recent_activity": []
        }
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Assuming 'profile_view' event is logged in `analytics_events` or similar
                # Let's count contact clicks from `lead_analytics` first
                cur.execute("""
                    SELECT COUNT(*) as count 
                    FROM lead_analytics 
                    WHERE provider_id = %s
                """, (provider_id,))
                res = cur.fetchone()
                stats["total_clicks"] = res["count"] if res else 0

                cur.execute("""
                    SELECT COUNT(*) as count 
                    FROM lead_analytics 
                    WHERE provider_id = %s AND created_at >= NOW() - INTERVAL '7 days'
                """, (provider_id,))
                res = cur.fetchone()
                stats["clicks_7d"] = res["count"] if res else 0

                cur.execute("""
                    SELECT contact_method, COUNT(*) as count
                    FROM lead_analytics
                    WHERE provider_id = %s
                    GROUP BY contact_method
                """, (provider_id,))
                for row in cur.fetchall():
                    method = row.get("contact_method")
                    if method:
                        stats["clicks_by_method"][method] = row["count"]

                # We can construct a basic 7-day trend array
                cur.execute("""
                    SELECT DATE(created_at) as date_val, COUNT(*) as count
                    FROM lead_analytics
                    WHERE provider_id = %s AND created_at >= NOW() - INTERVAL '7 days'
                    GROUP BY DATE(created_at)
                    ORDER BY date_val ASC
                """, (provider_id,))
                stats["recent_activity"] = [dict(row) for row in cur.fetchall()]

            return stats
        except Exception as e:
            logger.error(f"Error getting provider analytics stats: {e}")
            return stats

    def get_provider_public_trust_stats(self, provider_id: int) -> Dict:
        """Builds public trust stats (views/contact conversion + last contact time)."""
        stats = {
            "views_30d": 0,
            "contacts_30d": 0,
            "response_rate_pct": None,
            "last_contact_at": None,
        }
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM analytics_events
                    WHERE event_name = 'profile_view'
                      AND (event_payload->>'provider_id') = %s
                      AND created_at >= NOW() - INTERVAL '30 days'
                    """,
                    (str(provider_id),),
                )
                row = cur.fetchone()
                stats["views_30d"] = int(row["count"]) if row and row.get("count") is not None else 0

                cur.execute(
                    """
                    SELECT COUNT(*) AS count, MAX(created_at) AS last_contact_at
                    FROM lead_analytics
                    WHERE provider_id = %s
                      AND created_at >= NOW() - INTERVAL '30 days'
                    """,
                    (provider_id,),
                )
                row = cur.fetchone()
                if row:
                    stats["contacts_30d"] = int(row["count"]) if row.get("count") is not None else 0
                    stats["last_contact_at"] = row.get("last_contact_at")

                views = int(stats["views_30d"] or 0)
                contacts = int(stats["contacts_30d"] or 0)
                if views > 0:
                    conversion = int(round((contacts / views) * 100))
                    stats["response_rate_pct"] = max(0, min(99, conversion))

            return stats
        except Exception as e:
            logger.error(f"Error getting public trust stats for provider {provider_id}: {e}")
            try:
                self.conn.rollback()
            except Exception:
                pass
            return stats

    def get_portal_ops_metrics(self) -> Dict:
        """Aggregates operational metrics for portal signups and activation funnel."""
        metrics = {
            "generated_at": datetime.utcnow(),
            "registrations_total": 0,
            "registrations_24h": 0,
            "registrations_7d": 0,
            "verifications_total": 0,
            "verifications_7d": 0,
            "onboarding_completed_total": 0,
            "onboarding_completed_7d": 0,
            "trial_activations_total": 0,
            "trial_activations_7d": 0,
            "live_providers_total": 0,
            "live_providers_online": 0,
            "pending_review_total": 0,
        }
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*) AS registrations_total,
                        COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '24 hours') AS registrations_24h,
                        COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days') AS registrations_7d,
                        COUNT(*) FILTER (WHERE COALESCE(email_verified, FALSE) = TRUE) AS verifications_total,
                        COUNT(*) FILTER (WHERE COALESCE(portal_onboarding_complete, FALSE) = TRUE) AS onboarding_completed_total,
                        COUNT(*) FILTER (WHERE trial_started_at IS NOT NULL) AS trial_activations_total,
                        COUNT(*) FILTER (WHERE COALESCE(is_active, FALSE) = TRUE) AS live_providers_total,
                        COUNT(*) FILTER (WHERE COALESCE(is_active, FALSE) = TRUE AND COALESCE(is_online, FALSE) = TRUE) AS live_providers_online,
                        COUNT(*) FILTER (WHERE COALESCE(account_state, 'pending_review') = 'pending_review') AS pending_review_total
                    FROM providers
                    WHERE COALESCE(auth_channel, 'telegram') = 'portal'
                    """
                )
                row = cur.fetchone() or {}
                for key in [
                    "registrations_total",
                    "registrations_24h",
                    "registrations_7d",
                    "verifications_total",
                    "onboarding_completed_total",
                    "trial_activations_total",
                    "live_providers_total",
                    "live_providers_online",
                    "pending_review_total",
                ]:
                    metrics[key] = int(row.get(key) or 0)

                cur.execute(
                    """
                    SELECT COUNT(DISTINCT pve.provider_id) AS verifications_7d
                    FROM provider_verification_events pve
                    JOIN providers p ON p.id = pve.provider_id
                    WHERE pve.event_type = 'email_verified'
                      AND pve.created_at >= NOW() - INTERVAL '7 days'
                      AND COALESCE(p.auth_channel, 'telegram') = 'portal'
                    """
                )
                row = cur.fetchone() or {}
                metrics["verifications_7d"] = int(row.get("verifications_7d") or 0)

                cur.execute(
                    """
                    SELECT COUNT(DISTINCT pve.provider_id) AS onboarding_completed_7d
                    FROM provider_verification_events pve
                    JOIN providers p ON p.id = pve.provider_id
                    WHERE pve.event_type = 'profile_submitted'
                      AND pve.created_at >= NOW() - INTERVAL '7 days'
                      AND COALESCE(p.auth_channel, 'telegram') = 'portal'
                    """
                )
                row = cur.fetchone() or {}
                metrics["onboarding_completed_7d"] = int(row.get("onboarding_completed_7d") or 0)

                cur.execute(
                    """
                    SELECT COUNT(*) AS trial_activations_7d
                    FROM providers
                    WHERE COALESCE(auth_channel, 'telegram') = 'portal'
                      AND trial_started_at >= NOW() - INTERVAL '7 days'
                    """
                )
                row = cur.fetchone() or {}
                metrics["trial_activations_7d"] = int(row.get("trial_activations_7d") or 0)

            return metrics
        except Exception as e:
            logger.error(f"Error getting portal ops metrics: {e}")
            try:
                self.conn.rollback()
            except Exception:
                pass
            return metrics

