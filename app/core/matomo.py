import asyncio
import hashlib
import hmac

import httpx
from loguru import logger
from starlette.requests import Request

from app.core.config import settings

# Shared client, created in start() only when tracking is configured; None means tracking is off.
_client: httpx.AsyncClient | None = None
# Hits still being sent; holding a reference keeps the tasks from being garbage collected.
_pending: set[asyncio.Task] = set()


def start() -> None:
    global _client
    if settings.MATOMO_SITE_ID is not None:
        # The connection limit caps concurrent hits; hits waiting for a connection give up
        # after the pool timeout, so a slow Matomo can't pile up open connections.
        _client = httpx.AsyncClient(timeout=5, limits=httpx.Limits(max_connections=10))


async def stop() -> None:
    """Give in-flight hits a few seconds to finish, then close the client."""
    global _client
    if _client is None:
        return
    if _pending:
        await asyncio.wait(_pending, timeout=5)
    await _client.aclose()
    _client = None


def build_hit(request: Request) -> dict:
    """Build the Matomo tracking parameters for one API request."""
    ua = request.headers.get("user-agent", "")
    params = {
        "idsite": settings.MATOMO_SITE_ID,
        "rec": 1,
        "apiv": 1,
        "send_image": 0,
        # Path only: query strings would make every search and typeahead keystroke its own page.
        "url": str(request.url.replace(query="")),
        "action_name": request.url.path,
        "ua": ua,
        "urlref": request.headers.get("referer", ""),
        "lang": request.headers.get("accept-language", ""),
    }
    ip = request.client.host if request.client else None
    # Matomo ignores cip (the caller's IP) unless the request carries a token with write access.
    if settings.MATOMO_TOKEN and ip:
        params.update(
            token_auth=settings.MATOMO_TOKEN,
            cip=ip,
            # API clients send no Matomo cookie, so derive a stable visitor id from IP + user
            # agent. Keyed with the token so the id can't be reversed into the caller's IP;
            # rotating the token resets visitor ids.
            cid=hmac.new(settings.MATOMO_TOKEN.encode(), f"{ip}|{ua}".encode(),
                         hashlib.sha256).hexdigest()[:16],
        )
    return params


async def send_hit(params: dict) -> None:
    try:
        response = await _client.post(f"{settings.MATOMO_URL}/matomo.php", data=params)
        response.raise_for_status()
    except Exception as e:
        # Tracking must never affect the API, whatever goes wrong.
        logger.warning(f"Matomo tracking failed: {e!r}")


class MatomoTrackingMiddleware:
    """Record each API request in Matomo, after the response, without delaying it.

    Disabled unless MATOMO_SITE_ID is set (see start()). CORS preflight (OPTIONS) requests are
    skipped so a browser call is counted once.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or _client is None or scope["method"] == "OPTIONS":
            await self.app(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        finally:
            task = asyncio.create_task(send_hit(build_hit(Request(scope))))
            _pending.add(task)
            task.add_done_callback(_pending.discard)
