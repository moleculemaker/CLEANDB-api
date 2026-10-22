import csv
from io import StringIO
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import app.routers.search as search
from app.core.config import settings
from app.db.database import get_db
from app.main import app
from app.models.clean_data import CLEANColumn

HEADER = [c.value for c in CLEANColumn]


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def db_calls():
    """Mock the DB query functions; iter_filtered_data yields the rows in db_calls.rows."""
    class Calls:
        rows = []
        streamed_params = []

    async def iter_filtered_data(db, params):
        Calls.streamed_params.append(params.model_copy())
        for row in Calls.rows:
            yield row

    with (
        patch.object(search, "iter_filtered_data", iter_filtered_data),
        patch.object(search, "has_more_rows_than", AsyncMock(return_value=False)) as more,
        patch.object(search, "get_total_count", AsyncMock()) as count,
        patch.object(search, "get_filtered_data", AsyncMock()) as fetch,
    ):
        Calls.has_more_rows_than, Calls.get_total_count, Calls.get_filtered_data = more, count, fetch
        yield Calls


def get_csv(client, query="accession=P51451"):
    return client.get(f"/api/v1/search?{query}&format=csv")


def parse(response):
    assert response.status_code == 200, response.text
    return list(csv.reader(StringIO(response.text)))


def make_row(**overrides):
    row = {c.value: None for c in CLEANColumn}
    row.update(accession="P51451", protein_name='Kinase, "BLK"')
    row.update(overrides)
    return row


def test_csv_joins_array_columns(client, db_calls):
    db_calls.rows = [make_row(
        clean_ec_number_array=["2.7.10.2", "2.7.11.1"],
        clean_ec_confidence_array=[0.98, 0.12],
        annot_ec_number_array=None,
    )]
    rows = parse(get_csv(client, "accession=P51451&limit=10"))

    assert rows[0] == HEADER
    record = dict(zip(HEADER, rows[1]))
    assert record["protein_name"] == 'Kinase, "BLK"'
    assert record["clean_ec_number_array"] == "2.7.10.2;2.7.11.1"
    assert record["clean_ec_confidence_array"] == "0.98;0.12"
    assert record["annot_ec_number_array"] == ""


def test_csv_has_header_when_no_rows_match(client, db_calls):
    assert parse(get_csv(client)) == [HEADER]


def test_csv_without_limit_returns_all_rows_up_to_cap(client, db_calls):
    db_calls.rows = [make_row(accession=f"P{i:05d}") for i in range(settings.AUTO_PAGINATION_THRESHOLD + 1)]
    rows = parse(get_csv(client, "offset=7"))

    assert len(rows) == 1 + settings.AUTO_PAGINATION_THRESHOLD + 1
    assert db_calls.streamed_params[0].limit == settings.CSV_MAX_ROWS
    assert db_calls.streamed_params[0].offset == 7
    db_calls.has_more_rows_than.assert_awaited_once()
    assert db_calls.has_more_rows_than.await_args.args[2] == settings.CSV_MAX_ROWS
    db_calls.get_total_count.assert_not_awaited()
    db_calls.get_filtered_data.assert_not_awaited()


def test_csv_without_limit_rejects_more_rows_than_cap(client, db_calls):
    db_calls.has_more_rows_than.return_value = True
    response = get_csv(client)

    assert response.status_code == 400
    assert f"more than {settings.CSV_MAX_ROWS} records" in response.json()["detail"]
    assert db_calls.streamed_params == []


def test_csv_with_limit_skips_cap_check(client, db_calls):
    parse(get_csv(client, "limit=50&offset=100"))

    assert db_calls.streamed_params[0].limit == 50
    assert db_calls.streamed_params[0].offset == 100
    db_calls.has_more_rows_than.assert_not_awaited()


def test_csv_db_error_mid_result_returns_500(client):
    async def failing_rows(db, params):
        yield make_row()
        raise RuntimeError("connection lost")

    with (
        patch.object(search, "iter_filtered_data", failing_rows),
        patch.object(search, "has_more_rows_than", AsyncMock(return_value=False)),
    ):
        response = get_csv(client)

    assert response.status_code == 500
    assert "connection lost" in response.json()["detail"]


def test_csv_spills_large_output_to_disk(client, db_calls):
    db_calls.rows = [make_row(protein_sequence="M" * 100_000) for _ in range(100)]
    rows = parse(get_csv(client))

    assert len(rows) == 101
    assert all(len(dict(zip(HEADER, r))["protein_sequence"]) == 100_000 for r in rows[1:])


def test_csv_rejects_limit_above_cap(client, db_calls):
    response = get_csv(client, f"limit={settings.CSV_MAX_ROWS + 1}")

    assert response.status_code == 400
    assert response.json()["detail"] == f"limit cannot exceed {settings.CSV_MAX_ROWS} for CSV responses"
    assert db_calls.streamed_params == []
