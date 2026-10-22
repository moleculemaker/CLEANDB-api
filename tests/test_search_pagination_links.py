import re
from urllib.parse import parse_qs, urlsplit

# One of every /search filter, using the query parameter names clients send
FILTERS = (
    "accession=P51451&organism=Homo%20sapiens&organism=Mus%20musculus&protein=Kinase"
    "&gene_name=BLK&ec_number=2.7.10.2&uniprot=BLK_HUMAN&curation_status=reviewed"
    "&clean_ec_confidence_min=0.5&clean_ec_confidence_max=0.9&sequence_length=100"
    "&ordering=-accession"
)

# One of every /typeahead search context filter
TYPEAHEAD_FILTERS = (
    "field_name=organism&search=homo&accession=P51451&organism=Homo%20sapiens&protein=Kinase"
    "&gene_name=BLK&ec_number=2.7.10.2&uniprot=BLK_HUMAN&curation_status=reviewed"
    "&clean_ec_confidence_min=0.5&clean_ec_confidence_max=0.9&sequence_length=100"
)


def queries(db):
    """The SQL and arguments of the last COUNT and data queries, ignoring LIMIT and OFFSET."""
    def normalize(call):
        sql = re.sub(r"\b(LIMIT|OFFSET) \d+", r"\1 _", call.args[0])
        return " ".join(sql.split()), call.args[1:]

    return normalize(db.fetchval.call_args), normalize(db.fetch.call_args)


def follow(client, db, url):
    """Request url and return the queries it ran. Fails if it never reached the DB."""
    db.fetchval.reset_mock()
    db.fetch.reset_mock()
    parts = urlsplit(url)
    response = client.get(f"{parts.path}?{parts.query}")
    assert response.status_code == 200, response.text
    return queries(db)


def link_params(url):
    return parse_qs(urlsplit(url).query)


def test_next_and_previous_keep_every_filter(client, db):
    db.fetchval.return_value = 100
    response = client.get(f"/api/v1/search?{FILTERS}&limit=10&offset=20")
    original_queries = queries(db)
    original = parse_qs(FILTERS)

    links = {name: response.json()[name] for name in ("next", "previous")}
    for name, offset in (("next", "30"), ("previous", "10")):
        assert link_params(links[name]) == {**original, "limit": ["10"], "offset": [offset]}, name
        assert follow(client, db, links[name]) == original_queries, name


def test_next_uses_the_default_page_size_when_no_limit_given(client, db):
    db.fetchval.return_value = 10_000
    response = client.get("/api/v1/search?ec_number=1.1.1.1")

    assert link_params(response.json()["next"]) == {
        "ec_number": ["1.1.1.1"], "limit": ["5000"], "offset": ["5000"],
    }


def test_previous_past_the_end_goes_to_the_last_page(client, db):
    db.fetchval.return_value = 36_682
    body = client.get("/api/v1/search?ec_number=1.1.1.1&limit=10&offset=100000").json()

    assert body["next"] is None
    assert link_params(body["previous"])["offset"] == ["36672"]


def test_previous_past_the_end_of_no_results_goes_to_the_start(client, db):
    db.fetchval.return_value = 0
    body = client.get("/api/v1/search?ec_number=1.1.1.1&limit=10&offset=50").json()

    assert link_params(body["previous"])["offset"] == ["0"]


def test_typeahead_next_and_previous_keep_every_filter(client, db):
    db.fetchval.return_value = 100
    response = client.get(f"/api/v1/typeahead?{TYPEAHEAD_FILTERS}&limit=10&offset=20")
    original_queries = queries(db)
    original = parse_qs(TYPEAHEAD_FILTERS)

    links = {name: response.json()[name] for name in ("next", "previous")}
    for name, offset in (("next", "30"), ("previous", "10")):
        assert link_params(links[name]) == {**original, "limit": ["10"], "offset": [offset]}, name
        assert follow(client, db, links[name]) == original_queries, name


def test_typeahead_previous_past_the_end_goes_to_the_last_page(client, db):
    db.fetchval.return_value = 50
    body = client.get("/api/v1/typeahead?field_name=organism&search=homo&offset=1000").json()

    assert body["next"] is None
    assert link_params(body["previous"]) == {
        "field_name": ["organism"], "search": ["homo"], "limit": ["20"], "offset": ["30"],
    }
