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
        description="The unique accession number/identifier from the Uniprot database: https://www.uniprot.org/ for the enzyme catalyzing the reaction in question",
    )
    protein_name: Optional[List[str]] = Field(
        None,
        description='Whether the enzyme catalyzing the reaction is "wild-type" (unmutated) or a mutant enzyme.',
    )
    organism: Optional[List[str]] = Field(
        None,
        description="The pH at which the data for the enzyme catalyzed reaction was collected.",
    )
    gene_name: Optional[List[str]] = Field(
        None, description="The unit of measurement for the kcat value"
    )
    ec_number: Optional[List[str]] = Field(
        None, description="The unit of measurement for the kcat value"
    )
    ec_confidence: Optional[float] = Field(
        None, description="The unit of measurement for the kcat value"
    )
    sequence_length: Optional[int] = Field(
        None, description="The unit of measurement for the kcat value"
    )

    # Numeric range filters (removed as requested)

    # PubMed ID filters (removed as requested)

    # Response format and pagination
    format: Optional[ResponseFormat] = Field(
        ResponseFormat.JSON, description="Response format (json or csv)"
    )
    columns: Optional[List[str]] = Field(
        None, description="Columns to include in the response"
    )
    limit: Optional[int] = Field(
        None, description="Maximum number of records to return"
    )
    offset: Optional[int] = Field(0, description="Number of records to skip")
