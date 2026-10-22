from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.db.database import get_db
from app.main import app

# Postgres rejects a negative LIMIT or OFFSET at execution time, which these
# endpoints turn into a 500. They should be rejected as bad input instead.
URLS = [
    "/api/v1/search?accession=P51451&limit=-1",
    "/api/v1/search?accession=P51451&offset=-5",
    "/api/v1/typeahead?field_name=organism&search=homo&limit=-1",
    "/api/v1/typeahead?field_name=organism&search=homo&offset=-5",
]


@pytest.fixture
def db():
    db = AsyncMock()
    db.fetch.return_value = []
    db.fetchval.return_value = 0
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.clear()


@pytest.mark.parametrize("url", URLS)
def test_negative_pagination_is_rejected(db, url):
    response = TestClient(app).get(url)

    assert 400 <= response.status_code < 500, response.text
    db.fetch.assert_not_called()
    db.fetchval.assert_not_called()
