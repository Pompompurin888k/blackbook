"""Helpers for running blocking DB repository calls off the event loop."""
from __future__ import annotations

from typing import Any, Callable

from fastapi.concurrency import run_in_threadpool


async def db_call(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Executes a synchronous DB call in FastAPI's threadpool."""
    return await run_in_threadpool(func, *args, **kwargs)
