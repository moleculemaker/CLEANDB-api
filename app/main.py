from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.core.config import settings
from app.db.database import _db
from app.routers import search


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for database connection handling."""
    # Connect to database on startup
    await _db.connect()
    yield
    # Disconnect from database on shutdown
    await _db.disconnect()


# Initialize FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION
    + f"""

## Automatic Pagination

When a query would return more than {settings.AUTO_PAGINATION_THRESHOLD} records and no explicit limit is
provided, the API will automatically paginate results to return {settings.AUTO_PAGINATION_THRESHOLD} records
at a time. The response will include pagination metadata with links to navigate
to next and previous pages.

This threshold can be configured using the AUTO_PAGINATION_THRESHOLD environment variable.

## How to Use

The CLEAN Data API provides programmatic access to enzyme EC number predictions generated
by the [CLEAN tool](https://github.com/tttianhao/CLEAN). You can query the database by
organism, protein name, gene name, UniProt accession, EC number, curation status, EC
confidence score, and sequence length.

**Base URL:** `https://fastapi.cleandb.mmli2.ncsa.illinois.edu/api/v1`

**Available Endpoints:**
- `GET /search` — Search and filter enzyme records
- `GET /typeahead` — Retrieve typeahead suggestions for a given field and search term
- `GET /ec_lookup` — Look up EC numbers or enzyme class names
- `GET /curation-statuses` — List available curation status options

Use the interactive documentation below to explore query parameters and response schemas,
or refer to the Python examples in the next section to get started quickly.

## Python Examples

The following examples use the [requests](https://docs.python-requests.org/) library.
Install it with `pip install requests` if needed.

### Search by organism name

```python
import requests

BASE_URL = "https://fastapi.cleandb.mmli2.ncsa.illinois.edu/api/v1"

response = requests.get(
    f"{{BASE_URL}}/search",
    params={{"organism": "Homo sapiens"}},
)
response.raise_for_status()
data = response.json()
print(f"Total results: {{data['total']}}")
for record in data["data"]:
    print(record["uniprot"], record["predicted_ec"])
```

### Search by EC number

```python
import requests

BASE_URL = "https://fastapi.cleandb.mmli2.ncsa.illinois.edu/api/v1"

response = requests.get(
    f"{{BASE_URL}}/search",
    params={{"ec_number": "3.5.1.18"}},
)
response.raise_for_status()
data = response.json()
print(f"Total results: {{data['total']}}")
for record in data["data"]:
    print(record["accession"], record["organism"])
```

### Filter by EC confidence and curation status

```python
import requests

BASE_URL = "https://fastapi.cleandb.mmli2.ncsa.illinois.edu/api/v1"

response = requests.get(
    f"{{BASE_URL}}/search",
    params={{
        "clean_ec_confidence_min": 0.9,
        "curation_status": "reviewed",
        "limit": 100,
        "offset": 0,
    }},
)
response.raise_for_status()
data = response.json()
print(f"Total results: {{data['total']}}")
for record in data["data"]:
    print(record["accession"], record["predicted_ec"])
```

### Download results as CSV

```python
import requests

BASE_URL = "https://fastapi.cleandb.mmli2.ncsa.illinois.edu/api/v1"

response = requests.get(
    f"{{BASE_URL}}/search",
    params={{"organism": "Escherichia coli", "format": "csv"}},
)
response.raise_for_status()
with open("cleandb_results.csv", "wb") as f:
    f.write(response.content)
print("Results saved to cleandb_results.csv")
```

### Typeahead suggestions for organism field

```python
import requests

BASE_URL = "https://fastapi.cleandb.mmli2.ncsa.illinois.edu/api/v1"

response = requests.get(
    f"{{BASE_URL}}/typeahead",
    params={{"field_name": "organism", "search": "Homo"}},
)
response.raise_for_status()
data = response.json()
print(data["matches"])
```

### Look up EC numbers by name or number

```python
import requests

BASE_URL = "https://fastapi.cleandb.mmli2.ncsa.illinois.edu/api/v1"

response = requests.get(
    f"{{BASE_URL}}/ec_lookup",
    params={{"search": "hydrolase"}},
)
response.raise_for_status()
data = response.json()
for match in data["matches"]:
    print(match["ec_number"], match["ec_name"])
```

## Data License

The CLEAN Data API provides access to enzyme EC number predictions produced by the CLEAN
machine-learning tool, combined with protein annotations sourced from
[UniProt](https://www.uniprot.org/).

**UniProt data** is made available under the
[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)
license. See the [UniProt license page](https://www.uniprot.org/help/license) for details.

**CLEAN predictions** are provided for research and educational use. If you use this data
in your research, please cite:

> Tianhao Yu, Haiyang Cui, Jianan Canal Li, Yunan Luo, Guangde Jiang, Huimin Zhao.
> *Enzyme function prediction using contrastive learning.*
> **Science**, 379(6639), 1358-1363 (2023).
> [https://doi.org/10.1126/science.adf2465](https://doi.org/10.1126/science.adf2465)

This API and its source code are released under the
[MIT License](https://opensource.org/licenses/MIT).
""",
    version=settings.VERSION,
    lifespan=lifespan,
    # Increase timeout and response size limits
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Length"],
    max_age=600,
)

# Add GZip compression middleware to compress large responses
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include API routers
app.include_router(search.router, prefix="/api/v1")
