"""Migrate existing local provider photo URLs from /static/uploads to Cloudflare R2.

Usage:
  python scripts/migrate_local_photos_to_r2.py            # dry run
  python scripts/migrate_local_photos_to_r2.py --apply    # upload and update DB
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
WEB_DIR = SCRIPT_DIR.parent
ROOT_DIR = WEB_DIR.parent
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import (  # noqa: E402
    CF_R2_ACCESS_KEY_ID,
    CF_R2_BUCKET,
    CF_R2_ENDPOINT,
    CF_R2_PUBLIC_BASE_URL,
    CF_R2_SECRET_ACCESS_KEY,
    ENABLE_CLOUDFLARE_R2_UPLOADS,
)
logger = logging.getLogger("migrate_local_photos_to_r2")


@dataclass
class MigrationStats:
    providers_seen: int = 0
    providers_changed: int = 0
    local_refs_found: int = 0
    planned_uploads: int = 0
    uploaded: int = 0
    missing_files: int = 0
    failed_uploads: int = 0


def _r2_ready() -> bool:
    return all(
        [
            ENABLE_CLOUDFLARE_R2_UPLOADS,
            CF_R2_BUCKET,
            CF_R2_ENDPOINT,
            CF_R2_ACCESS_KEY_ID,
            CF_R2_SECRET_ACCESS_KEY,
            CF_R2_PUBLIC_BASE_URL,
        ]
    )


def _normalize_local_upload_url(photo_ref: str) -> Optional[str]:
    """Return canonical /static/uploads path when photo_ref points to local uploads."""
    value = str(photo_ref or "").strip()
    if not value:
        return None

    normalized = value.replace("\\", "/")
    if normalized.startswith(("http://", "https://")):
        normalized = urlparse(normalized).path
    if normalized.startswith("static/uploads/providers/"):
        normalized = f"/{normalized}"
    if normalized.startswith("/uploads/providers/"):
        normalized = f"/static{normalized}"
    if "/static/uploads/providers/" in normalized:
        normalized = normalized[normalized.index("/static/uploads/providers/") :]

    if not normalized.startswith("/static/uploads/providers/"):
        return None
    return normalized


def _local_ref_to_disk_path(photo_ref: str) -> Optional[Path]:
    """Map a local photo URL/reference to disk path under web/static."""
    canonical = _normalize_local_upload_url(photo_ref)
    if not canonical:
        return None

    static_root = Path("static").resolve()
    upload_root = (static_root / "uploads/providers").resolve()
    candidate = (static_root / canonical[len("/static/") :]).resolve()
    try:
        candidate.relative_to(upload_root)
    except ValueError:
        return None
    return candidate


def _to_string_list(value) -> list[str]:
    """Normalize database photo values into a list of strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
        if "," in text:
            return [item.strip() for item in text.split(",") if item.strip()]
        return [text]
    return []


def _iter_candidates(conn, provider_id: Optional[int], limit: Optional[int]) -> Iterable[dict]:
    query = [
        "SELECT id, profile_photos",
        "FROM providers",
        "WHERE profile_photos IS NOT NULL",
        "  AND jsonb_typeof(profile_photos) = 'array'",
    ]
    params: list[object] = []
    if provider_id is not None:
        query.append("  AND id = %s")
        params.append(provider_id)
    query.append("ORDER BY id ASC")
    if limit is not None:
        query.append("LIMIT %s")
        params.append(limit)

    with conn.cursor() as cur:
        cur.execute("\n".join(query), tuple(params))
        return cur.fetchall()


def _process_provider(
    conn,
    provider: dict,
    apply_changes: bool,
    verbose: bool,
    stats: MigrationStats,
    upload_fn: Callable[..., Optional[str]],
) -> None:
    provider_id = int(provider["id"])
    photos = _to_string_list(provider.get("profile_photos"))
    updated_photos = list(photos)
    provider_changed = False
    provider_local_refs = 0

    for index, photo_ref in enumerate(photos):
        local_path = _local_ref_to_disk_path(photo_ref)
        if local_path is None:
            continue

        provider_local_refs += 1
        stats.local_refs_found += 1

        if not local_path.exists():
            stats.missing_files += 1
            logger.warning(
                "Provider %s: local file not found for %s (%s)",
                provider_id,
                photo_ref,
                local_path,
            )
            continue

        if not apply_changes:
            stats.planned_uploads += 1
            continue

        try:
            data = local_path.read_bytes()
        except OSError as err:
            stats.failed_uploads += 1
            logger.error("Provider %s: failed reading %s (%s)", provider_id, local_path, err)
            continue

        extension = local_path.suffix.lower() or ".jpg"
        uploaded_url = upload_fn(
            provider_id=provider_id,
            data=data,
            extension=extension,
            prefix="profile",
        )
        if not uploaded_url:
            stats.failed_uploads += 1
            logger.error("Provider %s: failed uploading %s to R2", provider_id, local_path)
            continue

        updated_photos[index] = uploaded_url
        stats.uploaded += 1
        provider_changed = True

        if verbose:
            logger.info("Provider %s: %s -> %s", provider_id, photo_ref, uploaded_url)

    if apply_changes and provider_changed:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE providers SET profile_photos = %s::jsonb WHERE id = %s",
                (json.dumps(updated_photos), provider_id),
            )
        conn.commit()
        stats.providers_changed += 1
        logger.info("Provider %s: updated photo list in database", provider_id)
    elif apply_changes and provider_local_refs > 0 and verbose:
        logger.info("Provider %s: no DB update needed", provider_id)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate provider photo URLs from local /static uploads to Cloudflare R2."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply uploads and database updates. Without this flag, runs in dry-run mode.",
    )
    parser.add_argument(
        "--provider-id",
        type=int,
        default=None,
        help="Only process one provider ID.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of providers scanned.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-photo progress details.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s:%(name)s:%(message)s",
    )

    if args.apply and not _r2_ready():
        print("R2 config is incomplete. Set R2 env vars before running with --apply.")
        return 2

    from database import Database  # noqa: WPS433,E402
    from services.storage_service import upload_provider_photo  # noqa: WPS433,E402

    db = Database()
    stats = MigrationStats()

    try:
        providers = list(_iter_candidates(db.conn, args.provider_id, args.limit))
    except Exception as err:
        print(f"Failed fetching providers: {err}")
        return 1

    if not providers:
        print("No providers with profile photos found.")
        return 0

    for provider in providers:
        stats.providers_seen += 1
        try:
            _process_provider(
                db.conn,
                provider,
                args.apply,
                args.verbose,
                stats,
                upload_provider_photo,
            )
        except Exception as err:
            stats.failed_uploads += 1
            try:
                db.conn.rollback()
            except Exception:
                pass
            logger.error("Provider %s: migration error (%s)", provider.get("id"), err)

    mode = "apply" if args.apply else "dry-run"
    print(f"Mode: {mode}")
    print(f"Providers scanned: {stats.providers_seen}")
    print(f"Local refs found: {stats.local_refs_found}")
    if args.apply:
        print(f"Uploaded to R2: {stats.uploaded}")
        print(f"Providers updated: {stats.providers_changed}")
        print(f"Failed uploads: {stats.failed_uploads}")
    else:
        print(f"Planned uploads: {stats.planned_uploads}")
    print(f"Missing local files: {stats.missing_files}")

    if args.apply and stats.failed_uploads > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
