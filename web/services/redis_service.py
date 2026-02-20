"""
Redis Service — rate limiting, page caching, and key management.
"""
import hashlib
import logging
from typing import Optional
from urllib.parse import urlparse

from config import ENABLE_REDIS_RATE_LIMITING, REDIS_URL, ENABLE_ARQ_PAYMENT_QUEUE

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None

try:
    from arq import create_pool
    from arq.connections import RedisSettings
except ImportError:  # pragma: no cover
    create_pool = None
    RedisSettings = None

from payment_queue_utils import extract_callback_reference, build_payment_callback_job_id

logger = logging.getLogger(__name__)

_redis_client = None
_redis_unavailable = False
_arq_pool = None
_arq_unavailable = False


def _rate_limit_key_suffix(value: str) -> str:
    raw = (value or "unknown").strip().lower().encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _get_redis_client():
    """Returns a connected Redis client or None when disabled/unavailable."""
    global _redis_client, _redis_unavailable
    if not ENABLE_REDIS_RATE_LIMITING or redis is None or _redis_unavailable:
        return None
    if _redis_client is not None:
        return _redis_client

    try:
        _redis_client = redis.Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
            health_check_interval=30,
        )
        _redis_client.ping()
        logger.info("Redis rate limiting enabled.")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis unavailable, falling back to DB rate controls: {e}")
        _redis_unavailable = True
        _redis_client = None
        return None


def _redis_consume_limit(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Consumes one token from a fixed window counter."""
    client = _get_redis_client()
    if client is None:
        return True, limit

    safe_limit = max(1, int(limit))
    safe_window = max(1, int(window_seconds))
    try:
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, safe_window)
        remaining = max(0, safe_limit - count)
        return count <= safe_limit, remaining
    except Exception as e:
        logger.warning(f"Redis consume failed for key {key}: {e}")
        return True, safe_limit


def _redis_reset_limit(key: str) -> None:
    """Clears a rate-limit key after successful auth."""
    client = _get_redis_client()
    if client is None:
        return
    try:
        client.delete(key)
    except Exception as e:
        logger.warning(f"Redis reset failed for key {key}: {e}")


def _cache_key(*parts: object) -> str:
    normalized = [str(part).strip().lower() if part is not None else "none" for part in parts]
    return "cache:" + ":".join(normalized)


def _redis_get_text(key: str) -> Optional[str]:
    client = _get_redis_client()
    if client is None:
        return None
    try:
        value = client.get(key)
        return str(value) if value else None
    except Exception as e:
        logger.warning(f"Redis get failed for key {key}: {e}")
        return None


def _redis_set_text(key: str, value: str, ttl_seconds: int) -> None:
    client = _get_redis_client()
    if client is None:
        return
    try:
        client.setex(key, max(1, int(ttl_seconds)), value)
    except Exception as e:
        logger.warning(f"Redis set failed for key {key}: {e}")


def _arq_redis_settings():
    if RedisSettings is None:
        return None
    parsed = urlparse(REDIS_URL)
    if parsed.scheme not in {"redis", "rediss"}:
        return RedisSettings()
    db_path = (parsed.path or "/0").lstrip("/") or "0"
    try:
        database = int(db_path)
    except ValueError:
        database = 0
    return RedisSettings(
        host=parsed.hostname or "redis",
        port=parsed.port or 6379,
        database=database,
        password=parsed.password,
        ssl=(parsed.scheme == "rediss"),
    )


async def _get_arq_pool():
    global _arq_pool, _arq_unavailable
    if not ENABLE_ARQ_PAYMENT_QUEUE or create_pool is None or _arq_unavailable:
        return None
    if _arq_pool is not None:
        return _arq_pool
    settings = _arq_redis_settings()
    if settings is None:
        return None
    try:
        _arq_pool = await create_pool(settings)
        logger.info("ARQ payment queue enabled.")
        return _arq_pool
    except Exception as e:
        logger.warning(f"ARQ unavailable, using inline callback processing: {e}")
        _arq_unavailable = True
        _arq_pool = None
        return None


async def _enqueue_payment_callback(payload: dict) -> bool:
    pool = await _get_arq_pool()
    if pool is None:
        return False
    reference = extract_callback_reference(payload)
    job_id = build_payment_callback_job_id(reference)
    try:
        job = await pool.enqueue_job("process_payment_callback_job", payload, _job_id=job_id)
        if job is None and job_id:
            logger.info(f"Payment callback already queued: {job_id}")
            return True
        return job is not None
    except Exception as e:
        logger.warning(f"Failed to enqueue payment callback job: {e}")
        return False
