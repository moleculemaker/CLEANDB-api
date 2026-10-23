import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

import app.core.matomo as matomo
from app.core.config import settings
from app.main import app


@pytest.fixture
def tracking(monkeypatch):
    monkeypatch.setattr(settings, "MATOMO_SITE_ID", 7)
    monkeypatch.setattr(settings, "MATOMO_TOKEN", None)
    with patch.object(matomo, "send_hit", AsyncMock()) as send_hit:
        yield send_hit


async def request(method, path, **kwargs):
    transport = httpx.ASGITransport(app=app, client=("203.0.113.5", 4321))
    async with httpx.AsyncClient(transport=transport, base_url="https://cleandb-api.test") as client:
        response = await client.request(method, path, **kwargs)
    await asyncio.gather(*matomo._pending)
    return response


async def test_records_request(tracking):
    response = await request("GET", "/api/v1/openapi.json?x=1",
                             headers={"user-agent": "curl/8", "referer": "https://example.org/"})
    assert response.status_code == 200
    params = tracking.await_args.args[0]
    assert params["idsite"] == 7
    assert params["rec"] == 1
    assert params["url"] == "https://cleandb-api.test/api/v1/openapi.json?x=1"
    assert params["action_name"] == "/api/v1/openapi.json"
    assert params["ua"] == "curl/8"
    assert params["urlref"] == "https://example.org/"
    assert len(params["cid"]) == 16
    assert "cip" not in params and "token_auth" not in params


async def test_visitor_id_depends_on_ip_and_user_agent(tracking):
    await request("GET", "/api/v1/openapi.json", headers={"user-agent": "a"})
    await request("GET", "/api/v1/openapi.json", headers={"user-agent": "a"})
    await request("GET", "/api/v1/openapi.json", headers={"user-agent": "b"})
    cids = [c.args[0]["cid"] for c in tracking.await_args_list]
    assert cids[0] == cids[1] != cids[2]


async def test_token_sends_caller_ip(tracking, monkeypatch):
    monkeypatch.setattr(settings, "MATOMO_TOKEN", "secret")
    await request("GET", "/api/v1/openapi.json")
    params = tracking.await_args.args[0]
    assert params["token_auth"] == "secret"
    assert params["cip"] == "203.0.113.5"


async def test_records_failed_requests(tracking):
    response = await request("GET", "/api/v1/no-such-endpoint")
    assert response.status_code == 404
    tracking.assert_awaited_once()


async def test_skips_cors_preflight(tracking):
    await request("OPTIONS", "/api/v1/search",
                  headers={"origin": "https://example.org", "access-control-request-method": "GET"})
    tracking.assert_not_awaited()


async def test_disabled_without_site_id(tracking, monkeypatch):
    monkeypatch.setattr(settings, "MATOMO_SITE_ID", None)
    response = await request("GET", "/api/v1/openapi.json")
    assert response.status_code == 200
    tracking.assert_not_awaited()


async def test_send_failure_is_logged_not_raised(monkeypatch):
    # Nothing listens on port 9, so the POST fails to connect.
    monkeypatch.setattr(settings, "MATOMO_URL", "http://127.0.0.1:9")
    with patch.object(matomo.logger, "warning") as warning:
        await matomo.send_hit({"idsite": 7, "rec": 1})
    warning.assert_called_once()
