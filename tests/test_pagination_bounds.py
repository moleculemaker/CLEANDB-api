import pytest

SEARCH = "/api/v1/search?accession=P51451"
TYPEAHEAD = "/api/v1/typeahead?field_name=organism&search=homo"
TOO_BIG = 2**63  # one past Postgres bigint

# Out-of-range values used to reach the SQL: negative or oversized ones made
# Postgres fail (a 500), and limit=0 gave /search a `next` link to the same page.
REJECTED = [
    (SEARCH, "limit", -1),
    (SEARCH, "limit", 0),
    (SEARCH, "limit", 100001),
    (SEARCH, "offset", -5),
    (SEARCH, "offset", TOO_BIG),
    (TYPEAHEAD, "limit", -1),
    (TYPEAHEAD, "limit", 0),
    (TYPEAHEAD, "limit", 101),
    (TYPEAHEAD, "offset", -5),
    (TYPEAHEAD, "offset", TOO_BIG),
]

ACCEPTED = [
    (SEARCH, "limit", 100000),
    (SEARCH, "offset", TOO_BIG - 1),
    (TYPEAHEAD, "limit", 100),
    (TYPEAHEAD, "offset", TOO_BIG - 1),
]


@pytest.mark.parametrize("url, param, value", REJECTED)
def test_out_of_range_pagination_is_rejected(client, db, url, param, value):
    response = client.get(f"{url}&{param}={value}")

    assert response.status_code == 422, response.text
    assert [e["loc"] for e in response.json()["detail"]] == [["query", param]]
    db.fetch.assert_not_called()
    db.fetchval.assert_not_called()


@pytest.mark.parametrize("url, param, value", ACCEPTED)
def test_pagination_bounds_are_inclusive(client, db, url, param, value):
    response = client.get(f"{url}&{param}={value}")

    assert response.status_code == 200, response.text
    assert f"{param.upper()} {value}" in db.fetch.call_args.args[0]
