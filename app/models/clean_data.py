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

    predictions_uniprot_annot_id: Optional[str] = Field(
        None,
        description="",
    )
    uniprot_id: Optional[str] = Field(
        None,
        description="",
    )
    curation_status: Optional[str] = Field(
        None,
        description="",
    )
    accession: Optional[str] = Field(
        None,
        description="",
    )
    protein_name: Optional[str] = Field(
        None,
        description='',
    )
    organism: Optional[float] = Field(
        None,
        description="",
    )
    ncbi_taxid: Optional[float] = Field(
        None,
        description="",
    )
    amino_acids: Optional[str] = Field(
        None, description=""
    )
    protein_sequence: Optional[float] = Field(
        None,
        description="",
    )
    enzyme_function: Optional[float] = Field(
        None,
        description="",
    )
    gene_name: Optional[str] = Field(
        None, description=""
    )
    clean_ec_number_array: Optional[List[str]] = Field(
        None,
        description = ""
    )
    clean_ec_confidence_array: Optional[List[float]] = Field(
        None,
        description = ""
    )
    annot_ec_number_array: Optional[List[str]] = Field(
        None,
        description = ""
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