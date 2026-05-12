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

# User Guide

The CLEAN Database API provides programmatic access to the same enzyme annotations and
CLEAN-predicted EC numbers available through the
[CLEAN Database user interface](https://cleandb.frontend.staging.mmli2.ncsa.illinois.edu).

This page serves as the API documentation, detailing available endpoints, request parameters,
response formats, and example usage. There are also interactive features to test endpoints
directly from your browser.

## Endpoint Documentation, Python Examples, and Interactive Testing

Below you will find a list of available endpoints. Each endpoint appears as a colored box with a
title and brief description. You can click on any endpoint to expand it and see more details,
including:
- **Description**: A brief overview of the endpoint's purpose.
- **Example Usage**: Sample code snippets in Python demonstrating how to call the endpoint and
  handle the response.
- **Parameters**: Required and optional parameters for the endpoint.
- **Response Format**: The structure of the data returned by the endpoint.
- **Try it out**: An interactive feature that allows you to test the endpoint directly from this
  page.

### Technical Note: Automatic Pagination

When a query would return more than {settings.AUTO_PAGINATION_THRESHOLD} records and no explicit
limit is provided, the API will automatically paginate results to return
{settings.AUTO_PAGINATION_THRESHOLD} records at a time. The response will include pagination
metadata with links to navigate to next and previous pages.

This threshold can be configured using the `AUTO_PAGINATION_THRESHOLD` environment variable.

## Data License

The CLEAN Database dataset is licensed under the Creative Commons Attribution 4.0 International
License (CC BY 4.0). This means you are free to share and adapt the material for any purpose,
even commercially, as long as you give appropriate credit, provide a link to the license, and
indicate if changes were made.

Full license text: [https://creativecommons.org/licenses/by/4.0/](https://creativecommons.org/licenses/by/4.0/)

## Support

If you have any questions, issues, or feedback regarding the API, please reach out to us via
email at <cleandb-feedback@moleculemaker.org>.

""",
    version=settings.VERSION,
    lifespan=lifespan,
    # Increase timeout and response size limits
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    swagger_ui_parameters={"syntaxHighlight.theme": "obsidian"},
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
