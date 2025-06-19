from enum import Enum
from typing import List, Optional

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
        description="Uniprot Accession",
    )
    organism: Optional[List[str]] = Field(
        None,
        description="Organism Name",
    )
    protein_name: Optional[List[str]] = Field(
        None,
        description="Protein Name",
    )
    gene_name: Optional[List[str]] = Field(
        None, description="Gene Name"
    )
    ec_number: Optional[List[str]] = Field(
        None, description="CLEAN_EC"
    )
    ec_confidence: Optional[float] = Field(
        None, description="EC_Class"
    )
    sequence_length: Optional[str] = Field(
        None, description="Amino Acids"
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
