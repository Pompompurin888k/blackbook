"""
Seed or reset a fully completed local dummy portal provider.

Usage:
  python scripts/seed_dummy_portal_provider.py
  python scripts/seed_dummy_portal_provider.py --email test@example.com --password StrongPass123
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
WEB_DIR = SCRIPT_PATH.parents[1]
ROOT_DIR = SCRIPT_PATH.parents[2]
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database import Database  # noqa: E402
from psycopg2.extras import Json  # noqa: E402
from utils.auth import _hash_password  # noqa: E402


@dataclass(frozen=True)
class DummyProviderConfig:
    email: str
    password: str
    username: str
    display_name: str
    phone: str
    city: str
    neighborhood: str
    tier: str
    online: bool


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return default


def _next_synthetic_telegram_id(db: Database) -> int:
    with db.conn.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(MIN(telegram_id), 0) AS min_id
            FROM providers
            WHERE telegram_id < 0
            """
        )
        row = cur.fetchone() or {}
    min_id = int(_row_get(row, "min_id", 0) or 0)
    return (min_id - 1) if min_id < 0 else -1000001


def _ensure_provider_row(db: Database, cfg: DummyProviderConfig, password_hash: str) -> tuple[int, bool]:
    with db.conn.cursor() as cur:
        cur.execute(
            """
            SELECT id
            FROM providers
            WHERE LOWER(COALESCE(email, '')) = LOWER(%s)
            ORDER BY id DESC
            LIMIT 1
            """,
            (cfg.email,),
        )
        existing = cur.fetchone()
        if existing:
            return int(_row_get(existing, "id")), False

        synthetic_tg_id = _next_synthetic_telegram_id(db)
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
                account_state,
                portal_onboarding_complete,
                is_verified,
                is_active,
                is_online,
                email_verified,
                phone_verified
            )
            VALUES (%s, %s, %s, %s, %s, 'portal', %s, 'approved', TRUE, TRUE, TRUE, %s, TRUE, TRUE)
            RETURNING id
            """,
            (
                synthetic_tg_id,
                cfg.username,
                cfg.display_name,
                cfg.phone,
                cfg.email,
                password_hash,
                cfg.online,
            ),
        )
        created = cur.fetchone() or {}
        return int(_row_get(created, "id")), True


def seed_dummy_provider(cfg: DummyProviderConfig) -> dict[str, Any]:
    db = Database()
    password_hash = _hash_password(cfg.password)
    photos = [
        "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1487412720507-e7ab37603c6f?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=1000&q=80",
    ]
    services = ["GFE", "Massage", "Dinner Date", "Overnight"]
    languages = ["English", "Swahili"]

    try:
        provider_id, created = _ensure_provider_row(db, cfg, password_hash)
        with db.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE providers
                SET
                    telegram_username = %s,
                    display_name = %s,
                    phone = %s,
                    email = %s,
                    city = %s,
                    neighborhood = %s,
                    age = 27,
                    height_cm = 168,
                    weight_kg = 57,
                    build = 'Athletic',
                    gender = 'Female',
                    sexual_orientation = 'Bisexual',
                    nationality = 'Kenyan',
                    county = 'Nairobi',
                    services = %s,
                    bio = %s,
                    nearby_places = 'Sarit Centre, Westgate, Riverside Drive',
                    availability_type = 'Both',
                    languages = %s,
                    profile_photos = %s,
                    incalls_from = 3000,
                    outcalls_from = 5000,
                    video_url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                    rate_30min = 3000,
                    rate_1hr = 5000,
                    rate_2hr = 9000,
                    rate_3hr = 13000,
                    rate_overnight = 25000,
                    auth_channel = 'portal',
                    portal_password_hash = %s,
                    phone_verified = TRUE,
                    email_verified = TRUE,
                    account_state = 'approved',
                    portal_onboarding_complete = TRUE,
                    is_verified = TRUE,
                    is_active = TRUE,
                    is_online = %s,
                    subscription_tier = %s,
                    credits = 0,
                    trial_used = TRUE,
                    trial_started_at = COALESCE(trial_started_at, NOW() - INTERVAL '2 days'),
                    approved_at = COALESCE(approved_at, NOW()),
                    approved_by_admin = COALESCE(approved_by_admin, 0),
                    rejection_reason = NULL,
                    login_failed_attempts = 0,
                    locked_until = NULL,
                    last_login_attempt_at = NOW(),
                    verification_code_hash = NULL,
                    verification_code_expires_at = NULL,
                    verification_code_used_at = NOW(),
                    password_reset_code_hash = NULL,
                    password_reset_code_expires_at = NULL,
                    password_reset_code_used_at = NOW(),
                    referral_code = COALESCE(referral_code, CONCAT('DUMMY', id::text))
                WHERE id = %s
                RETURNING id, telegram_id, display_name, email, phone, city, neighborhood,
                          account_state, email_verified, phone_verified, portal_onboarding_complete,
                          is_verified, is_active, is_online, subscription_tier, referral_code,
                          jsonb_array_length(COALESCE(profile_photos, '[]'::jsonb)) AS photos_count,
                          jsonb_array_length(COALESCE(services, '[]'::jsonb)) AS services_count,
                          jsonb_array_length(COALESCE(languages, '[]'::jsonb)) AS languages_count
                """,
                (
                    cfg.username,
                    cfg.display_name,
                    cfg.phone,
                    cfg.email,
                    cfg.city,
                    cfg.neighborhood,
                    Json(services),
                    "Discreet and polished companion for local development and QA profile flows.",
                    Json(languages),
                    Json(photos),
                    password_hash,
                    cfg.online,
                    cfg.tier,
                    provider_id,
                ),
            )
            row = cur.fetchone() or {}
        db.conn.commit()
        result = dict(row)
        result["created"] = created
        return result
    except Exception:
        db.conn.rollback()
        raise


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create or reset a fully completed local dummy portal provider."
    )
    parser.add_argument(
        "--email",
        default="dummy.provider.local@blackbook.test",
        help="Portal login email for the dummy provider.",
    )
    parser.add_argument(
        "--password",
        default="DevDummy@123",
        help="Portal login password for the dummy provider.",
    )
    parser.add_argument(
        "--display-name",
        default="Amina Dev Dummy",
        help="Visible provider display name.",
    )
    parser.add_argument(
        "--username",
        default="dummy_provider_local",
        help="Portal username (letters, numbers, underscores).",
    )
    parser.add_argument(
        "--phone",
        default="254712345678",
        help="Provider phone in 2547XXXXXXXX format.",
    )
    parser.add_argument("--city", default="Nairobi")
    parser.add_argument("--neighborhood", default="Westlands")
    parser.add_argument(
        "--tier",
        default="gold",
        choices=["none", "silver", "gold", "platinum"],
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Create provider as offline (is_online=false).",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    cfg = DummyProviderConfig(
        email=args.email.strip().lower(),
        password=args.password,
        username=args.username.strip().lower().lstrip("@"),
        display_name=args.display_name.strip(),
        phone=args.phone.strip(),
        city=args.city.strip(),
        neighborhood=args.neighborhood.strip(),
        tier=args.tier.strip().lower(),
        online=not args.offline,
    )
    result = seed_dummy_provider(cfg)
    print("Dummy portal provider ready.")
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    print("")
    print("Login URL: http://127.0.0.1:8080/provider")
    print(f"Email: {cfg.email}")
    print(f"Password: {cfg.password}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
