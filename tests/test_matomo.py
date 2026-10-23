import asyncio
import hashlib
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from starlette.requests import Request

import app.core.matomo as matomo
from app.core.config import Settings, settings
from app.main import app


@pytest.fixture
async def tracking(monkeypatch):
    monkeypatch.setattr(settings, "MATOMO_SITE_ID", 7)
    monkeypatch.setattr(settings, "MATOMO_TOKEN", None)
    matomo.start()
    with patch.object(matomo, "send_hit", AsyncMock()) as send_hit:
        yield send_hit
    await matomo.stop()


async def request(method, path, **kwargs):
    transport = httpx.ASGITransport(app=app, client=("203.0.113.5", 4321))
    async with httpx.AsyncClient(transport=transport, base_url="https://cleandb-api.test") as client:
        response = await client.request(method, path, **kwargs)
    await asyncio.gather(*matomo._pending)
    return response


async def test_records_request_path_without_query(tracking):
    response = await request("GET", "/api/v1/openapi.json?accession=P51451",
                             headers={"user-agent": "curl/8", "referer": "https://example.org/"})
    assert response.status_code == 200
    params = tracking.await_args.args[0]
    assert params["idsite"] == 7
    assert params["rec"] == 1
    assert params["url"] == "https://cleandb-api.test/api/v1/openapi.json"
    assert params["action_name"] == "/api/v1/openapi.json"
    assert params["ua"] == "curl/8"
    assert params["urlref"] == "https://example.org/"
    assert not {"cip", "cid", "token_auth"} & params.keys()


async def test_token_sends_caller_ip_and_keyed_visitor_id(tracking, monkeypatch):
    monkeypatch.setattr(settings, "MATOMO_TOKEN", "secret")
    await request("GET", "/api/v1/openapi.json", headers={"user-agent": "a"})
    await request("GET", "/api/v1/openapi.json", headers={"user-agent": "a"})
    await request("GET", "/api/v1/openapi.json", headers={"user-agent": "b"})
    first, again, other_ua = (c.args[0] for c in tracking.await_args_list)
    assert first["token_auth"] == "secret"
    assert first["cip"] == "203.0.113.5"
    assert len(first["cid"]) == 16
    assert first["cid"] == again["cid"] != other_ua["cid"]
    # Not recoverable by hashing candidate IPs and user agents without the token.
    assert first["cid"] != hashlib.sha256(b"203.0.113.5|a").hexdigest()[:16]

    monkeypatch.setattr(settings, "MATOMO_TOKEN", "other")
    await request("GET", "/api/v1/openapi.json", headers={"user-agent": "a"})
    assert tracking.await_args.args[0]["cid"] != first["cid"]


def test_no_caller_address_sends_no_ip_or_visitor_id(monkeypatch):
    monkeypatch.setattr(settings, "MATOMO_TOKEN", "secret")
    scope = {"type": "http", "method": "GET", "scheme": "https", "server": ("api.test", 443),
             "path": "/api/v1/search", "query_string": b"", "headers": [], "client": None}
    params = matomo.build_hit(Request(scope))
    assert not {"cip", "cid", "token_auth"} & params.keys()


async def test_records_failed_requests(tracking):
    response = await request("GET", "/api/v1/no-such-endpoint")
    assert response.status_code == 404
    tracking.assert_awaited_once()


async def test_skips_cors_preflight(tracking):
    await request("OPTIONS", "/api/v1/search",
                  headers={"origin": "https://example.org", "access-control-request-method": "GET"})
    tracking.assert_not_awaited()


async def test_disabled_without_site_id(monkeypatch):
    monkeypatch.setattr(settings, "MATOMO_SITE_ID", None)
    matomo.start()
    with patch.object(matomo, "send_hit", AsyncMock()) as send_hit:
        response = await request("GET", "/api/v1/openapi.json")
    assert response.status_code == 200
    send_hit.assert_not_awaited()


def test_empty_settings_mean_unset(monkeypatch):
    monkeypatch.setenv("MATOMO_SITE_ID", "")
    monkeypatch.setenv("MATOMO_TOKEN", "")
    loaded = Settings(_env_file=None)
    assert loaded.MATOMO_SITE_ID is None
    assert loaded.MATOMO_TOKEN is None


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:9",  # nothing listens on port 9, so the POST fails to connect
    "http://matomo:not-a-port",  # httpx.InvalidURL, which is not an httpx.HTTPError
])
async def test_send_failure_is_logged_not_raised(monkeypatch, url):
    monkeypatch.setattr(settings, "MATOMO_SITE_ID", 7)
    monkeypatch.setattr(settings, "MATOMO_URL", url)
    matomo.start()
    with patch.object(matomo.logger, "warning") as warning:
        await matomo.send_hit({"idsite": 7, "rec": 1})
    await matomo.stop()
    warning.assert_called_once()


async def test_stop_waits_for_in_flight_hits(monkeypatch):
    monkeypatch.setattr(settings, "MATOMO_SITE_ID", 7)
    matomo.start()

    async def slow_post(*args, **kwargs):
        await asyncio.sleep(0.1)
        return httpx.Response(204, request=httpx.Request("POST", "https://matomo.test"))

    with patch.object(matomo._client, "post", side_effect=slow_post) as post:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://cleandb-api.test") as client:
            await client.get("/api/v1/openapi.json")
        assert matomo._pending
        await matomo.stop()
    post.assert_awaited_once()
    assert not matomo._pending
    assert matomo._client is None
