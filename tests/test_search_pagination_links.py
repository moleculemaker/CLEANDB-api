from urllib.parse import parse_qs, urlsplit

# One of every /search filter, using the query parameter names clients send
FILTERS = (
    "accession=P51451&organism=Homo%20sapiens&organism=Mus%20musculus&protein=Kinase"
    "&gene_name=BLK&ec_number=2.7.10.2&uniprot=BLK_HUMAN&curation_status=reviewed"
    "&clean_ec_confidence_min=0.5&clean_ec_confidence_max=0.9&sequence_length=100"
    "&ordering=-accession"
)


def where_clause(db):
    query = db.fetchval.call_args.args[0]
    return " ".join(query.split("WHERE", 1)[1].split())


def follow(client, url):
    parts = urlsplit(url)
    return client.get(f"{parts.path}?{parts.query}")


def test_next_and_previous_keep_every_filter(client, db):
    db.fetchval.return_value = 100
    response = client.get(f"/api/v1/search?{FILTERS}&limit=10&offset=20")
    original_where = where_clause(db)
    original = parse_qs(FILTERS)

    links = {name: response.json()[name] for name in ("next", "previous")}
    for name, offset in (("next", "30"), ("previous", "10")):
        params = parse_qs(urlsplit(links[name]).query)
        assert params == {**original, "limit": ["10"], "offset": [offset]}, name

        follow(client, links[name])
        assert where_clause(db) == original_where, name


def test_next_uses_the_default_page_size_when_no_limit_given(client, db):
    db.fetchval.return_value = 10_000
    response = client.get("/api/v1/search?ec_number=1.1.1.1")

    params = parse_qs(urlsplit(response.json()["next"]).query)
    assert params == {"ec_number": ["1.1.1.1"], "limit": ["5000"], "offset": ["5000"]}
