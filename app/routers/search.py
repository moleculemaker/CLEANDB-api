import csv
from io import StringIO
from typing import Any, List, Literal, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from app.core.config import settings
from app.db.database import Database, get_db
from app.db.queries import get_ec_suggestions, get_filtered_data, get_total_count, get_typeahead_suggestions
from app.models.query_params import CLEANECLookupQueryParams, CLEANSearchQueryParams, CLEANTypeaheadQueryParams, ResponseFormat
from app.models.clean_data import CLEANDataBase, CLEANECLookupResponse, CLEANECLookupMatch, CLEANSearchResponse, CLEANTypeaheadResponse, CurationStatusOption, CLEANCurationStatusResponse

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
    curation_status: Optional[List[str]] = Query(
        None,
        description="Curation status (reviewed/unreviewed)"
    ),
    # Additional filters
    clean_ec_confidence_min: Optional[float] = Query(
        None, description="Minimum confidence for CLEAN predicted EC number"
    ),
    clean_ec_confidence_max: Optional[float] = Query(
        None, description="Maximum confidence for CLEAN predicted EC number"
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
    ordering: Optional[str] = Query(
        None,
        description="Column to sort by. Prefix with '-' for descending order. "
        "Allowed values: accession, amino_acids, organism, curation_status, predicted_ec",
    ),
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
            clean_ec_confidence_min = clean_ec_confidence_min,
            clean_ec_confidence_max = clean_ec_confidence_max,
            sequence_length = sequence_length,
            uniprot_id = uniprot,
            curation_status=curation_status,
            format=format,
            limit=limit,
            offset=offset,
            ordering=ordering,
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
        # Apply default page size if no explicit limit provided
        if params.limit is None:
            params.limit = settings.AUTO_PAGINATION_THRESHOLD

        # Get total count for the query (without pagination)
        total_count = await get_total_count(db, params)

        # Get data from database
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
            response = CLEANSearchResponse(
                total=total_count,
                offset=params.offset,
                limit=params.limit,
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

            # Add pagination links
            if request:
                base_url = str(request.url).split("?")[0]

                # Prepare query parameters for pagination links
                query_params = {
                    k: v
                    for k, v in params.model_dump().items()
                    if k not in ["auto_paginated", "offset", "limit"]
                    and v is not None
                }

                # Set format explicitly if it was provided
                if params.format != ResponseFormat.JSON:
                    query_params["format"] = params.format

                current_offset = params.offset or 0
                current_limit = params.limit

                # Next page link if there are more records
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

                # Previous page link if not on first page
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
    field_name: Literal['accession', 'organism', 'protein_name', 'gene_name', 'uniprot_id', 'predicted_ec'] = Query(
        'organism',
        description="Which field to search in",
    ),
    search: str = Query(
        None,
        min_length=3,
        description="Search term for typeahead suggestions (minimum 3 characters)"
    ),
    limit: Optional[int] = Query(
        20, description="Maximum number of records to return"
    ),
    offset: Optional[int] = Query(
        0, description="Number of records to skip"
    ),
    # Search context filters
    accession: Optional[List[str]] = Query(
        None, description="Filter typeahead results by accession"
    ),
    organism: Optional[List[str]] = Query(
        None, description="Filter typeahead results by organism"
    ),
    protein: Optional[List[str]] = Query(
        None, description="Filter typeahead results by protein name"
    ),
    gene_name: Optional[List[str]] = Query(
        None, description="Filter typeahead results by gene name"
    ),
    ec_number: Optional[List[str]] = Query(
        None, description="Filter typeahead results by CLEAN EC number"
    ),
    uniprot: Optional[List[str]] = Query(
        None, description="Filter typeahead results by uniprot ID"
    ),
    curation_status: Optional[List[str]] = Query(
        None, description="Filter typeahead results by curation status"
    ),
    clean_ec_confidence_min: Optional[float] = Query(
        None, description="Filter typeahead results by minimum CLEAN EC confidence"
    ),
    clean_ec_confidence_max: Optional[float] = Query(
        None, description="Filter typeahead results by maximum CLEAN EC confidence"
    ),
    sequence_length: Optional[str] = Query(
        None, description="Filter typeahead results by minimum sequence length"
    ),
) -> CLEANTypeaheadQueryParams:
    """Parse and validate query parameters."""
    try:
        return CLEANTypeaheadQueryParams(
            field_name=field_name,
            search=search,
            limit=limit,
            offset=offset,
            accession=accession,
            organism=organism,
            protein_name=protein,
            gene_name=gene_name,
            clean_ec_number=ec_number,
            uniprot_id=uniprot,
            curation_status=curation_status,
            clean_ec_confidence_min=clean_ec_confidence_min,
            clean_ec_confidence_max=clean_ec_confidence_max,
            sequence_length=sequence_length,
        )
    except Exception as e:
        logger.error(f"Error parsing query parameters: {e}")
        raise HTTPException(
            status_code=400, detail=f"Invalid query parameters: {str(e)}"
        )


def _build_search_context(params: CLEANTypeaheadQueryParams) -> Optional[dict]:
    """Build the search context dict from non-None context params."""
    context = {}
    if params.accession:
        context['accession'] = params.accession
    if params.organism:
        context['organism'] = params.organism
    if params.protein_name:
        context['protein_name'] = params.protein_name
    if params.gene_name:
        context['gene_name'] = params.gene_name
    if params.clean_ec_number:
        context['ec_number'] = params.clean_ec_number
    if params.uniprot_id:
        context['uniprot'] = params.uniprot_id
    if params.curation_status:
        context['curation_status'] = params.curation_status
    if params.clean_ec_confidence_min is not None:
        context['clean_ec_confidence_min'] = params.clean_ec_confidence_min
    if params.clean_ec_confidence_max is not None:
        context['clean_ec_confidence_max'] = params.clean_ec_confidence_max
    if params.sequence_length:
        context['sequence_length'] = params.sequence_length
    return context if context else None


@router.get("/typeahead", summary="Get typeahead suggestions for searching the database of predicted EC numbers.")
async def get_typeahead(
    params: CLEANTypeaheadQueryParams = Depends(parse_typeahead_params),
    db: Database = Depends(get_db),
    request: Request = None,
) -> CLEANTypeaheadResponse:
    """
    Get typeahead suggestions for searching the database of predicted EC numbers.
    """

    try:
        limit = params.limit or 20
        offset = params.offset or 0

        # Get data from database
        matches, total = await get_typeahead_suggestions(db, params)

        # Build search context
        search_context = _build_search_context(params)

        # Build pagination URLs
        next_url = None
        previous_url = None

        if request:
            base_url = str(request.url).split("?")[0]

            # Build base query params (excluding pagination)
            base_params = {
                "field_name": params.field_name,
                "search": params.search,
                "limit": limit,
            }

            # Add context params if present
            if params.accession:
                base_params["accession"] = params.accession
            if params.organism:
                base_params["organism"] = params.organism
            if params.protein_name:
                base_params["protein"] = params.protein_name
            if params.gene_name:
                base_params["gene_name"] = params.gene_name
            if params.clean_ec_number:
                base_params["ec_number"] = params.clean_ec_number
            if params.uniprot_id:
                base_params["uniprot"] = params.uniprot_id
            if params.curation_status:
                base_params["curation_status"] = params.curation_status
            if params.clean_ec_confidence_min is not None:
                base_params["clean_ec_confidence_min"] = params.clean_ec_confidence_min
            if params.clean_ec_confidence_max is not None:
                base_params["clean_ec_confidence_max"] = params.clean_ec_confidence_max
            if params.sequence_length:
                base_params["sequence_length"] = params.sequence_length

            # Next page
            if offset + limit < total:
                next_params = {**base_params, "offset": offset + limit}
                next_url = f"{base_url}?{urlencode(next_params, doseq=True)}"

            # Previous page
            if offset > 0:
                prev_offset = max(0, offset - limit)
                prev_params = {**base_params, "offset": prev_offset}
                previous_url = f"{base_url}?{urlencode(prev_params, doseq=True)}"

        return CLEANTypeaheadResponse(
            field_name=params.field_name,
            search=params.search,
            matches=matches,
            search_context=search_context,
            total=total,
            limit=limit,
            offset=offset,
            next=next_url,
            previous=previous_url,
        )

    except Exception as e:
        logger.error(f"Error getting data: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving data: {str(e)}")


@router.get("/curation-statuses", summary="Get available curation status options")
async def get_curation_statuses() -> CLEANCurationStatusResponse:
    """
    Get the list of available curation status options for filtering.
    """
    return CLEANCurationStatusResponse(
        statuses=[
            CurationStatusOption(value="reviewed", label="Reviewed (Swiss-Prot)"),
            CurationStatusOption(value="unreviewed", label="Unreviewed (TrEMBL)"),
        ]
    )


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
