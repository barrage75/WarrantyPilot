import logging
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlsplit

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.background import BackgroundTask, BackgroundTasks

from app.core.journal import auto_anchor

logger = logging.getLogger(__name__)

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


def _origin_of(value: str) -> str | None:
    parts = urlsplit(value)
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}".casefold()


def foreign_origin(request: Request, allowed: list[str]) -> str | None:
    allowed_origins = {origin.rstrip("/").casefold() for origin in allowed}
    origin = request.headers.get("origin")
    if origin is not None:
        normalized = _origin_of(origin)
        return origin if normalized is None or normalized not in allowed_origins else None
    referer = request.headers.get("referer")
    if referer is not None:
        normalized = _origin_of(referer)
        return referer if normalized is None or normalized not in allowed_origins else None
    return None


async def origin_guard_and_anchor(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if request.method in SAFE_METHODS:
        return await call_next(request)
    settings = request.app.state.app_settings
    if foreign_origin(request, settings.cors_origins) is not None:
        return JSONResponse(status_code=403, content={"detail": "Cross-origin request refused"})
    response = await call_next(request)
    if response.status_code < 400:
        response.background = _chain(
            response.background,
            BackgroundTask(_safe_auto_anchor, request.app.state.session_factory, settings),
        )
    return response


def _safe_auto_anchor(session_factory: Any, settings: Any) -> None:
    try:
        auto_anchor(session_factory, settings)
    except OperationalError:
        logger.warning("journal auto-anchor deferred: database busy")


def _chain(
    existing: BackgroundTask | None, task: BackgroundTask
) -> BackgroundTask | BackgroundTasks:
    if existing is None:
        return task
    tasks = BackgroundTasks()
    tasks.add_task(existing)
    tasks.add_task(task)
    return tasks
