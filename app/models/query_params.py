from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ResponseFormat(str, Enum):
    """Enum for response format options."""

    JSON = "json"
    CSV = "csv"


class CLEANSearchQueryParams(BaseModel):
    """Query parameters for CLEAN data filtering."""

    # Flag for automatic pagination
    auto_paginated: bool = Field(
        False, 
        description="Whether results are automatically paginated"
    )

    # String filters (exact match, case-insensitive, multiple values with OR logic)
    accession: Optional[List[str]] = Field(
        None,
        description="Uniprot Accession, case-insensitive exact match (multiple values allowed, OR logic)",
    )
    organism: Optional[List[str]] = Field(
        None,
        description="Organism Name, case-insensitive exact match (multiple values allowed, OR logic)",
    )
    protein_name: Optional[List[str]] = Field(
        None,
        description="Protein Name, case-insensitive exact match (multiple values allowed, OR logic)",
    )
    gene_name: Optional[List[str]] = Field(
        None, description="Gene Name, case-insensitive exact match (multiple values allowed, OR logic)"
    )
    uniprot_id: Optional[List[str]] = Field(
        None, description=""
    )
    clean_ec_number: Optional[List[str]] = Field(
        None, description="CLEAN predicted EC number, exact match or wildcard match using terminal dash (multiple values allowed, OR logic)"
    )
    clean_ec_confidence_min: Optional[float] = Field(
        None, description="Minimum confidence for CLEAN predicted EC number"
    )
    clean_ec_confidence_max: Optional[float] = Field(
        None, description="Maximum confidence for CLEAN predicted EC number"
    )
    sequence_length: Optional[str] = Field(
        None, description="Minimum sequence length"
    )
    curation_status: Optional[List[str]] = Field(
        None, description="Curation status filter (reviewed/unreviewed), case-insensitive exact match (multiple values allowed, OR logic)"
    )

    # Numeric range filters (removed as requested)

    # PubMed ID filters (removed as requested)

    # Response format and pagination
    format: Optional[ResponseFormat] = Field(
        ResponseFormat.JSON, description="Response format (json or csv)"
    )
    limit: Optional[int] = Field(
        None, description="Maximum number of records to return"
    )
    offset: Optional[int] = Field(0, description="Number of records to skip")
    ordering: Optional[str] = Field(
        None,
        description="Column to sort by. Prefix with '-' for descending order. "
        "Allowed values: accession, amino_acids, organism, curation_status, predicted_ec",
    )

class CLEANTypeaheadQueryParams(BaseModel):
    """Query parameters for CLEAN typeahead suggestions."""

    field_name: Literal['accession', 'organism', 'protein_name', 'gene_name', 'uniprot_id', 'predicted_ec'] = Field(
        'organism',
        description="Which field to search in",
    )
    search: str = Field(
        None,
        min_length=3,
        description="Search term for typeahead suggestions (minimum 3 characters)"
    )
    limit: Optional[int] = Field(
        None, description="Maximum number of records to return"
    )
    offset: Optional[int] = Field(
        0, description="Number of records to skip for pagination"
    )

    # Search context fields - when provided, typeahead results are filtered to match the current search context
    accession: Optional[List[str]] = Field(
        None, description="Filter typeahead results by accession"
    )
    organism: Optional[List[str]] = Field(
        None, description="Filter typeahead results by organism"
    )
    protein_name: Optional[List[str]] = Field(
        None, description="Filter typeahead results by protein name"
    )
    gene_name: Optional[List[str]] = Field(
        None, description="Filter typeahead results by gene name"
    )
    uniprot_id: Optional[List[str]] = Field(
        None, description="Filter typeahead results by uniprot ID"
    )
    clean_ec_number: Optional[List[str]] = Field(
        None, description="Filter typeahead results by CLEAN EC number"
    )
    curation_status: Optional[List[str]] = Field(
        None, description="Filter typeahead results by curation status"
    )
    clean_ec_confidence_min: Optional[float] = Field(
        None, description="Filter typeahead results by minimum CLEAN EC confidence"
    )
    clean_ec_confidence_max: Optional[float] = Field(
        None, description="Filter typeahead results by maximum CLEAN EC confidence"
    )
    sequence_length: Optional[str] = Field(
        None, description="Filter typeahead results by minimum sequence length"
    )

class CLEANECLookupQueryParams(BaseModel):
    """Query parameters for CLEAN EC lookup."""

    search: str = Field(
        None,
        description="A partial or full EC number or EC class name to search for"
    )
    limit: Optional[int] = Field(
        None, description="Maximum number of records to return"
    )