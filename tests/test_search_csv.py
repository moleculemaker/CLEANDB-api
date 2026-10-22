import csv
from io import StringIO
from unittest.mock import AsyncMock, patch

import app.routers.search as search
from app.models.clean_data import CLEANColumn

HEADER = [c.value for c in CLEANColumn]


def get_csv(client, rows):
    with (
        patch.object(search, "get_total_count", AsyncMock(return_value=len(rows))),
        patch.object(search, "get_filtered_data", AsyncMock(return_value=rows)),
    ):
        response = client.get("/api/v1/search?accession=P51451&format=csv&limit=10")
    assert response.status_code == 200, response.text
    return list(csv.reader(StringIO(response.text)))


def make_row(**overrides):
    row = {c.value: None for c in CLEANColumn}
    row.update(accession="P51451", protein_name='Kinase, "BLK"')
    row.update(overrides)
    return row


def test_csv_joins_array_columns(client):
    rows = get_csv(client, [make_row(
        clean_ec_number_array=["2.7.10.2", "2.7.11.1"],
        clean_ec_confidence_array=[0.98, 0.12],
        annot_ec_number_array=None,
    )])

    assert rows[0] == HEADER
    record = dict(zip(HEADER, rows[1]))
    assert record["protein_name"] == 'Kinase, "BLK"'
    assert record["clean_ec_number_array"] == "2.7.10.2;2.7.11.1"
    assert record["clean_ec_confidence_array"] == "0.98;0.12"
    assert record["annot_ec_number_array"] == ""


def test_csv_has_header_when_no_rows_match(client):
    assert get_csv(client, []) == [HEADER]
