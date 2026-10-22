import csv
from io import StringIO
from unittest.mock import AsyncMock, patch

import pytest

import app.routers.search as search
from app.core.config import settings
from app.models.clean_data import CLEANColumn

HEADER = [c.value for c in CLEANColumn]


@pytest.fixture
def db_calls():
    """Mock the DB query functions; iter_filtered_data yields the rows in db_calls.rows."""
    class Calls:
        rows = []
        streamed_params = []
        rows_closed = False

    async def iter_filtered_data(db, params):
        Calls.streamed_params.append(params.model_copy())
        try:
            for row in Calls.rows:
                yield row
        finally:
            Calls.rows_closed = True

    with (
        patch.object(search, "iter_filtered_data", iter_filtered_data),
        patch.object(search, "get_total_count", AsyncMock()) as count,
        patch.object(search, "get_filtered_data", AsyncMock()) as fetch,
    ):
        Calls.get_total_count, Calls.get_filtered_data = count, fetch
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


def test_csv_without_limit_returns_all_rows_up_to_cap(client, db_calls, monkeypatch):
    monkeypatch.setattr(search, "MAX_SEARCH_LIMIT", 3)
    db_calls.rows = [make_row(accession=f"P{i:05d}") for i in range(3)]
    rows = parse(get_csv(client, "offset=7"))

    assert [r[3] for r in rows[1:]] == ["P00000", "P00001", "P00002"]
    # One row past the cap is requested, so an oversized result can be detected
    assert db_calls.streamed_params[0].limit == 4
    assert db_calls.streamed_params[0].offset == 7
    db_calls.get_total_count.assert_not_awaited()
    db_calls.get_filtered_data.assert_not_awaited()


def test_csv_without_limit_rejects_more_rows_than_cap(client, db_calls, monkeypatch):
    monkeypatch.setattr(search, "MAX_SEARCH_LIMIT", 3)
    db_calls.rows = [make_row() for _ in range(4)]
    response = get_csv(client)

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Query matches more than 3 records")
    # The row iterator, and so the DB cursor, is closed as soon as the cap is passed
    assert db_calls.rows_closed


def test_csv_with_limit_is_not_capped(client, db_calls, monkeypatch):
    monkeypatch.setattr(search, "MAX_SEARCH_LIMIT", 3)
    db_calls.rows = [make_row() for _ in range(4)]
    rows = parse(get_csv(client, "limit=50&offset=100"))

    assert len(rows) == 5
    assert db_calls.streamed_params[0].limit == 50
    assert db_calls.streamed_params[0].offset == 100


def test_csv_db_error_mid_result_returns_500(client):
    async def failing_rows(db, params):
        yield make_row()
        raise RuntimeError("connection lost")

    with patch.object(search, "iter_filtered_data", failing_rows):
        response = get_csv(client)

    assert response.status_code == 500
    assert "connection lost" in response.json()["detail"]


def test_csv_spills_large_output_to_disk(client, db_calls):
    db_calls.rows = [make_row(protein_sequence="M" * 100_000) for _ in range(100)]
    rows = parse(get_csv(client))

    assert len(rows) == 101
    assert all(len(dict(zip(HEADER, r))["protein_sequence"]) == 100_000 for r in rows[1:])


async def test_closing_iter_filtered_data_closes_the_cursor(db):
    from contextlib import aclosing

    from app.db.queries import iter_filtered_data
    from app.models.query_params import CLEANSearchQueryParams

    closed = []

    async def iterate(query, *args):
        try:
            yield make_row()
            yield make_row()
        finally:
            closed.append(True)

    db.iterate = iterate
    async with aclosing(iter_filtered_data(db, CLEANSearchQueryParams(limit=2))) as rows:
        await anext(rows)

    assert closed == [True]


async def test_write_csv_closes_rows_when_over_cap():
    from fastapi import HTTPException

    closed = []

    async def rows():
        try:
            for _ in range(5):
                yield make_row()
        finally:
            closed.append(True)

    # Holding a reference means only an explicit close, not garbage collection, can close it
    generator = rows()
    with pytest.raises(HTTPException) as error:
        await search.write_csv(generator, max_rows=3)

    assert error.value.status_code == 400
    assert closed == [True]
