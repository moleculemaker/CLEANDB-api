import os
from unittest.mock import AsyncMock

import pytest

# Settings require DB credentials at import time; tests mock the DB calls.
for key in ("CLEAN_DB_HOST", "CLEAN_DB_USER", "CLEAN_DB_PASSWORD", "CLEAN_DB_NAME"):
    os.environ.setdefault(key, "test")
# Keep a developer's .env from sending test requests to the real Matomo site.
os.environ["MATOMO_SITE_ID"] = ""


@pytest.fixture
def db():
    db = AsyncMock()
    db.fetch.return_value = []
    db.fetchval.return_value = 0
    return db


@pytest.fixture
def client(db):
    # Imported here so the environment above is set before settings load.
    from fastapi.testclient import TestClient

    from app.db.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()
