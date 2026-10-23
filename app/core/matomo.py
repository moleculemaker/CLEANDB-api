import asyncio
import hashlib

import httpx
from loguru import logger
from starlette.requests import Request

from app.core.config import settings

# Hits still being sent; holding a reference keeps the tasks from being garbage collected.
_pending: set[asyncio.Task] = set()


def build_hit(request: Request) -> dict:
    """Build the Matomo tracking parameters for one API request."""
    ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")
    params = {
        "idsite": settings.MATOMO_SITE_ID,
        "rec": 1,
        "apiv": 1,
        "send_image": 0,
        "url": str(request.url),
        "action_name": request.url.path,
        "ua": ua,
        "urlref": request.headers.get("referer", ""),
        "lang": request.headers.get("accept-language", ""),
        # API clients send no Matomo cookie, so derive a stable visitor id from IP + user agent.
        "cid": hashlib.sha256(f"{ip}|{ua}".encode()).hexdigest()[:16],
    }
    # Matomo ignores cip (the caller's IP) unless the request carries a token with write access.
    if settings.MATOMO_TOKEN:
        params.update(token_auth=settings.MATOMO_TOKEN, cip=ip)
    return params


async def send_hit(params: dict) -> None:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(f"{settings.MATOMO_URL}/matomo.php", data=params)
            response.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning(f"Matomo tracking failed: {e!r}")


class MatomoTrackingMiddleware:
    """Record each API request in Matomo, after the response, without delaying it.

    Disabled unless MATOMO_SITE_ID is set. CORS preflight (OPTIONS) requests are skipped so a
    browser call is counted once.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or settings.MATOMO_SITE_ID is None or scope["method"] == "OPTIONS":
            await self.app(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        finally:
            task = asyncio.create_task(send_hit(build_hit(Request(scope))))
            _pending.add(task)
            task.add_done_callback(_pending.discard)
