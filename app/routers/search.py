import csv
from io import StringIO
from typing import Any, List, Literal, Optional, Union
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from app.core.config import settings
from app.db.database import Database, get_db
from app.db.queries import get_ec_suggestions, get_filtered_data, get_total_count, get_typeahead_suggestions
from app.models.query_params import CLEANECLookupQueryParams, CLEANSearchQueryParams, CLEANTypeaheadQueryParams, ResponseFormat
from app.models.clean_data import CLEANDataBase, CLEANECLookupResponse, CLEANECLookupMatch, CLEANSearchResponse, CLEANTypeaheadResponse

router = APIRouter(tags=["Search"])


def parse_query_params(
    # String filters
    accession: Optional[List[str]] = Query(
        None,
        description="Uniprot Accession",
    ),
    organism: Optional[List[str]] = Query(
        None,
        description="Organism Name",
    ),
    protein: Optional[List[str]] = Query(
        None,
        description="Protein Name",
    ),
    gene_name: Optional[List[str]] = Query(
        None,
        description="Gene Name"
    ),
    ec_number: Optional[List[str]] = Query(
        None,
        description="CLEAN predicted EC number"
    ),
    uniprot: Optional[List[str]] = Query(
        None,
        description="Uniprot ID"
    ),
    # Additional filters
    clean_ec_confidence: Optional[float] = Query(
        None, description="Minimum confidence for CLEAN predicted EC number"
    ),
    sequence_length: Optional[str] = Query(
        None, description="Minimum sequence length"
    ),
    # Response format and pagination
    format: ResponseFormat = Query(
        default=ResponseFormat.JSON, description="Response format (json or csv)"
    ),
    limit: Optional[int] = Query(
        None, description="Maximum number of records to return"
    ),
    offset: Optional[int] = Query(0, description="Number of records to skip"),
) -> CLEANSearchQueryParams:
    """Parse and validate query parameters."""
    try:
        # Validate format
        if format not in [fmt for fmt in ResponseFormat]:
            format = ResponseFormat.JSON

        return CLEANSearchQueryParams(
            accession=accession,
            protein_name=protein,
            organism=organism,
            gene_name=gene_name,
            clean_ec_number=ec_number,
            clean_ec_confidence = clean_ec_confidence,
            sequence_length = sequence_length,
            uniprot_id = uniprot,
            format=format,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.error(f"Error parsing query parameters: {e}")
        raise HTTPException(
            status_code=400, detail=f"Invalid query parameters: {str(e)}"
        )


@router.get("/search", summary="Get enzyme kinetic data")
async def get_data(
    params: CLEANSearchQueryParams = Depends(parse_query_params),
    db: Database = Depends(get_db),
    request: Request = None,
) -> CLEANSearchResponse:
    """
    Get enzyme kinetic data with filtering options.
    """

    try:
        # # Get total count for the query (without pagination)
        # total_count = await get_total_count(db, params)

        # # Apply automatic pagination if results exceed threshold and no explicit limit provided
        # if total_count > settings.AUTO_PAGINATION_THRESHOLD and params.limit is None:
        #     params.auto_paginated = True
        #     params.limit = settings.AUTO_PAGINATION_THRESHOLD
        #     logger.info(
        #         f"Auto-pagination applied. Results limited to {params.limit} records."
        #     )

        params.limit = 500
        # Get data from database (now with potential auto-pagination applied)
        data = await get_filtered_data(db, params)

        # Handle response format
        if params.format == ResponseFormat.CSV:
            # Create CSV response
            output = StringIO()

            # Determine columns to include in CSV
            if params.columns:
                fieldnames = params.columns
            elif data and len(data) > 0:
                fieldnames = list(data[0].keys())
            else:
                fieldnames = []

            # Write CSV
            writer = csv.DictWriter(
                output, fieldnames=fieldnames, extrasaction="ignore"
            )
            writer.writeheader()
            for row in data:
                writer.writerow(row)

            # Return streaming response
            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=CLEAN_data.csv"},
            )
        else:
            # TODO don't we want total_count to be the value returned by get_total_count?
            total_count = len(data)
            response = CLEANSearchResponse(
                total=total_count,
                offset=params.offset,
                limit=total_count if total_count < params.limit else params.limit,
                data=[CLEANDataBase(
                    predictions_uniprot_annot_id=record["predictions_uniprot_annot_id"],
                    uniprot=record["uniprot_id"],
                    curation_status=record["curation_status"],
                    accession=record["accession"],
                    protein=record["protein_name"],
                    organism=record["organism"],
                    ncbi_tax_id=record["ncbi_taxid"],
                    amino_acids=record["amino_acids"],
                    sequence=record["protein_sequence"],
                    function=record["enzyme_function"],
                    gene_name=record["gene_name"],
                    predicted_ec=[
                        {
                            "ec_number": ec,
                            "score": conf
                        }
                        for ec, conf in zip(record["clean_ec_number_array"], record["clean_ec_confidence_array"])
                    ],
                    annot_ec_number_array=record["annot_ec_number_array"]
                ) for record in data],
            )

            # Add pagination links if automatic pagination was applied
            if params.auto_paginated:
                # Add flag indicating automatic pagination was applied
                response.auto_paginated = True

                if request:
                    base_url = str(request.url).split("?")[0]

                    # Prepare query parameters for pagination links
                    # For Pydantic v2 compatibility
                    query_params = {
                        k: v
                        for k, v in params.model_dump().items()
                        if k not in ["auto_paginated", "offset", "limit"]
                        and v is not None
                    }

                    # Set format explicitly if it was provided
                    if params.format != ResponseFormat.JSON:
                        query_params["format"] = params.format

                    # Calculate next page link if there are more records
                    current_offset = params.offset or 0
                    current_limit = params.limit or total_count
                    if current_offset + current_limit < total_count:
                        next_offset = current_offset + current_limit
                        next_params = {
                            **query_params,
                            "offset": next_offset,
                            "limit": current_limit,
                        }
                        response.next = (
                            f"{base_url}?{urlencode(next_params, doseq=True)}"
                        )

                    # Calculate previous page link if not on first page
                    current_offset = params.offset or 0
                    current_limit = params.limit or total_count
                    if current_offset > 0:
                        prev_offset = max(0, current_offset - current_limit)
                        prev_params = {
                            **query_params,
                            "offset": prev_offset,
                            "limit": current_limit,
                        }
                        response.previous = (
                            f"{base_url}?{urlencode(prev_params, doseq=True)}"
                        )

            return response

    except Exception as e:
        logger.error(f"Error getting data: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving data: {str(e)}")

def parse_typeahead_params(
    field_name: Literal['accession', 'organism', 'protein_name', 'gene_name'] = Query(
        'organism',
        description="Which field to search in",
    ),
    search: str = Query(
        None,
        min_length=3,
        description="Search term for typeahead suggestions (minimum 3 characters)"
    )
) -> CLEANTypeaheadQueryParams:
    """Parse and validate query parameters."""
    try:
        return CLEANTypeaheadQueryParams(
            field_name=field_name,
            search=search,
        )
    except Exception as e:
        logger.error(f"Error parsing query parameters: {e}")
        raise HTTPException(
            status_code=400, detail=f"Invalid query parameters: {str(e)}"
        )

@router.get("/typeahead", summary="Get typeahead suggestions for enzyme kinetic data")
async def get_typeahead(
    params: CLEANTypeaheadQueryParams = Depends(parse_typeahead_params),
    db: Database = Depends(get_db),
    request: Request = None,
) -> CLEANTypeaheadResponse:
    """
    Get typeahead suggestions for enzyme kinetic data.
    """

    try:
        params.limit = 20
        # Get data from database
        data = await get_typeahead_suggestions(db, params)

        return CLEANTypeaheadResponse(
            field_name=params.field_name,
            search=params.search,
            matches=data
        )

    except Exception as e:
        logger.error(f"Error getting data: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving data: {str(e)}")

def parse_ec_lookup_params(
    search: str = Query(
        None,
        description="A partial or full EC number or EC class name to search for"
    )
) -> CLEANECLookupQueryParams:
    """Parse and validate query parameters."""
    try:
        return CLEANECLookupQueryParams(
            search=search,
        )
    except Exception as e:
        logger.error(f"Error parsing query parameters: {e}")
        raise HTTPException(
            status_code=400, detail=f"Invalid query parameters: {str(e)}"
        )

@router.get("/ec_lookup", summary="Look up EC numbers or classes")

async def get_ec_lookup(
    params: CLEANECLookupQueryParams = Depends(parse_ec_lookup_params),
    db: Database = Depends(get_db),
    request: Request = None,
) -> CLEANECLookupResponse:
    """
    Look up EC numbers or classes based on a search term.
    """

    try:
        params.limit = 20
        # Get data from database
        data = await get_ec_suggestions(db, params)

        return CLEANECLookupResponse(
            search=params.search,
            matches=[CLEANECLookupMatch(ec_number=item["ec_number"], ec_name=item["ec_name"]) for item in data]
        )

    except Exception as e:
        logger.error(f"Error getting data: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving data: {str(e)}")
