from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

import httpx
from arq.connections import RedisSettings

logger = logging.getLogger(__name__)


def build_redis_settings() -> RedisSettings:
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    parsed = urlparse(redis_url)
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


async def process_payment_callback_job(ctx, payload: dict):
    """Background processor for verified MegaPay callback payloads."""
    web_internal_base = os.getenv("WEB_INTERNAL_BASE_URL", "http://web:8080").rstrip("/")
    internal_token = os.getenv("INTERNAL_TASK_TOKEN", "")
    if not internal_token:
        raise RuntimeError("INTERNAL_TASK_TOKEN is required for queued payment processing")

    url = f"{web_internal_base}/payments/callback"
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Task-Token": internal_token,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=payload)
    if response.status_code >= 500:
        raise RuntimeError(f"Payment callback processing failed: {response.status_code} {response.text}")
    logger.info(f"Processed queued payment callback with status={response.status_code}")
    return {"status_code": response.status_code, "result": response.text}


class WorkerSettings:
    functions = [process_payment_callback_job]
    redis_settings = build_redis_settings()
    max_jobs = int(os.getenv("ARQ_MAX_JOBS", "10"))
    job_timeout = int(os.getenv("ARQ_JOB_TIMEOUT_SECONDS", "120"))
    keep_result = int(os.getenv("ARQ_KEEP_RESULT_SECONDS", "3600"))
