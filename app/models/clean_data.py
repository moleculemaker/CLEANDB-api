from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

class CLEANColumn(Enum):
    predictions_uniprot_annot_id = "predictions_uniprot_annot_id"
    uniprot_id = "uniprot_id"
    curation_status = "curation_status"
    accession = "accession"
    protein_name = "protein_name"
    organism = "organism"
    ncbi_taxid = "ncbi_taxid"
    amino_acids = "amino_acids"
    protein_sequence = "protein_sequence"
    enzyme_function = "enzyme_function"
    gene_name = "gene_name"
    clean_ec_number_array = "clean_ec_number_array"
    clean_ec_confidence_array = "clean_ec_confidence_array"
    annot_ec_number_array = "annot_ec_number_array"


class CLEANDataBase(BaseModel):
    """Base model for CLEAN data."""

    predictions_uniprot_annot_id: Optional[int] = Field(
        None,
        description="Unique identifier for the CLEAN predictions record.",
    )
    uniprot_id: Optional[str] = Field(
        None,
        description="Unique identifier for the Uniprot record.",
    )
    curation_status: Optional[str] = Field(
        None,
        description="Status of the curation for the Uniprot record.",
    )
    accession: Optional[str] = Field(
        None,
        description="Uniprot accession number.",
    )
    protein_name: Optional[str] = Field(
        None,
        description="Name of the protein associated with the Uniprot record.",
    )
    organism: Optional[str] = Field(
        None,
        description= "Name of the organism associated with the Uniprot record.",
    )
    ncbi_taxid: Optional[int] = Field(
        None,
        description="NCBI Taxonomy ID for the organism associated with the Uniprot record.",
    )
    amino_acids: Optional[int] = Field(
        None, description= "Length of the amino acid sequence associated with the Uniprot record.",
    )
    protein_sequence: Optional[str] = Field(
        None,
        description="Amino acid sequence of the protein associated with the Uniprot record.",
    )
    enzyme_function: Optional[str] = Field(
        None,
        description="Function of the enzyme associated with the Uniprot record.",
    )
    gene_name: Optional[str] = Field(
        None, description="Name of the gene associated with the Uniprot record.",
    )
    clean_ec_number_array: Optional[List[str]] = Field(
        None,
        description="List of CLEAN predicted EC numbers associated with the Uniprot record. Each EC number is a string.",
    )
    clean_ec_confidence_array: Optional[List[float]] = Field(
        None,
        description="List of confidence scores for each CLEAN predicted EC number. Each score is a float.",
    )
    annot_ec_number_array: Optional[List[str]] = Field(
        None,
        description="List of annotated EC numbers associated with the Uniprot record. Each EC number is a string.",
    )

class CLEANSearchResponse(BaseModel):
    """Model for the response of a CLEAN search query."""
    total: int = Field(
        0,
        description="Total number of records matching the query."
    )
    limit: Optional[int] = Field(
        None,
        description="Maximum number of records returned."
    )
    offset: Optional[int] = Field(
        0,
        description="Number of records skipped."
    )
    auto_paginated: Optional[bool] = Field(
        False,
        description="Whether results are automatically paginated."
    )
    next: Optional[str] = Field(
        None,
        description="Link to the next page of results."
    )
    previous: Optional[str] = Field(
        None,
        description="Link to the previous page of results."
    )
    data: List[CLEANDataBase] = Field(
        [],
        description="List of records matching the query."
    )

class CLEANTypeaheadResponse(BaseModel):
    """Model for the response of a CLEAN typeahead query."""
    field_name: Literal['accession', 'organism', 'protein_name', 'gene_name'] = Field(
        'organism',
        description="Which field to search in",
    ),
    search: str = Field(
        None,
        min_length=3,
        description="Search term for typeahead suggestions (minimum 3 characters)"
    )
    matches: List[str] = Field(
        [],
        description="List of results matching the search term."
    )

class CLEANECLookupMatch(BaseModel):
    """Model for a single match in the CLEAN EC lookup response."""
    ec_number: str = Field(
        None,
        description="EC number."
    )
    ec_name: str = Field(
        None,
        description="EC name."
    )

class CLEANECLookupResponse(BaseModel):
    search: str = Field(
        None,
        description="The search term used for the lookup."
    )
    matches: List[CLEANECLookupMatch] = Field(
        [],
        description="List of matches for the EC lookup."
    )