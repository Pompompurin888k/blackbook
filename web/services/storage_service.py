"""
Object storage helper for provider uploads.

Supports Cloudflare R2 (S3-compatible) with local filesystem fallback handled by callers.
"""
from __future__ import annotations

import logging
import mimetypes
import uuid
from typing import Optional

from config import (
    ENABLE_CLOUDFLARE_R2_UPLOADS,
    CF_R2_ACCESS_KEY_ID,
    CF_R2_BUCKET,
    CF_R2_ENDPOINT,
    CF_R2_PUBLIC_BASE_URL,
    CF_R2_REGION,
    CF_R2_SECRET_ACCESS_KEY,
    CF_R2_UPLOAD_PREFIX,
)

logger = logging.getLogger(__name__)

_s3_client = None
_missing_config_warned = False


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


def _get_r2_client():
    global _s3_client, _missing_config_warned
    if not _r2_ready():
        if ENABLE_CLOUDFLARE_R2_UPLOADS and not _missing_config_warned:
            logger.warning(
                "Cloudflare R2 uploads are enabled but config is incomplete; falling back to local storage."
            )
            _missing_config_warned = True
        return None

    if _s3_client is not None:
        return _s3_client

    try:
        import boto3
        from botocore.config import Config
    except Exception as err:
        logger.error("boto3/botocore import failed for R2 uploads: %s", err)
        return None

    try:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=CF_R2_ENDPOINT.rstrip("/"),
            aws_access_key_id=CF_R2_ACCESS_KEY_ID,
            aws_secret_access_key=CF_R2_SECRET_ACCESS_KEY,
            region_name=CF_R2_REGION,
            config=Config(signature_version="s3v4"),
        )
        return _s3_client
    except Exception as err:
        logger.error("Failed to initialize Cloudflare R2 client: %s", err)
        return None


def upload_provider_photo(
    provider_id: int,
    data: bytes,
    extension: str,
    prefix: str,
    content_type: Optional[str] = None,
) -> Optional[str]:
    """
    Uploads provider photo bytes to Cloudflare R2 and returns a public URL.
    Returns None when R2 is disabled/unavailable so caller can fallback to local disk.
    """
    client = _get_r2_client()
    if client is None:
        return None

    safe_ext = str(extension or ".jpg").strip().lower()
    if not safe_ext.startswith("."):
        safe_ext = f".{safe_ext}"
    object_name = f"{prefix}_{uuid.uuid4().hex}{safe_ext}"
    parts = [CF_R2_UPLOAD_PREFIX, str(provider_id), object_name]
    object_key = "/".join(part.strip("/") for part in parts if part and part.strip("/"))
    mime_type = content_type or mimetypes.types_map.get(safe_ext, "application/octet-stream")

    try:
        client.put_object(
            Bucket=CF_R2_BUCKET,
            Key=object_key,
            Body=data,
            ContentType=mime_type,
            CacheControl="public, max-age=31536000, immutable",
        )
    except Exception as err:
        logger.error("Cloudflare R2 upload failed: %s", err)
        return None

    return f"{CF_R2_PUBLIC_BASE_URL}/{object_key}"
