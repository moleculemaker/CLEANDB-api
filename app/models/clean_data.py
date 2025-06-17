from enum import Enum
from typing import List, Optional

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
        description="The Enzyme Commission Number, describing the type of reaction that is catalyzed by this enzyme. For examples of the EC Number hierarchy, please see the Open Enzyme Database Home Page, Statistics View.",
    )
    uniprot_id: Optional[str] = Field(
        None,
        description="The substrate (chemical compound) that is one of the reactants of the enzymatic reaction in question",
    )
    curation_status: Optional[str] = Field(
        None,
        description="The organism (e.g. human, horse) in which the data for the enzymatic reaction was measured",
    )
    accession: Optional[str] = Field(
        None,
        description="The unique accession number/identifier from the Uniprot database: https://www.uniprot.org/ for the enzyme catalyzing the reaction in question",
    )
    protein_name: Optional[str] = Field(
        None,
        description='Whether the enzyme catalyzing the reaction is "wild-type" (unmutated) or a mutant enzyme.',
    )
    organism: Optional[float] = Field(
        None,
        description="The pH at which the data for the enzyme catalyzed reaction was collected.",
    )
    ncbi_taxid: Optional[float] = Field(
        None,
        description="The temperature (in degrees Celsius) at which the data for the enzyme catalyzed reaction was collected.",
    )
    amino_acids: Optional[str] = Field(
        None, description="SMILES representation of the substrate chemical structure"
    )
    protein_sequence: Optional[float] = Field(
        None,
        description="The Michaelis-Menten catalytic rate constant (kcat) that was measured for the enzymatic reaction.",
    )
    enzyme_function: Optional[float] = Field(
        None,
        description="The PubMed Identifier (https://pubmed.ncbi.nlm.nih.gov/) for the experimental details from which the kcat data was collected.",
    )
    gene_name: Optional[str] = Field(
        None, description="The unit of measurement for the kcat value"
    )
    clean_ec_number_array: Optional[List[str]] = Field(
        None,
        description = ""
    ),
    clean_ec_confidence_array: Optional[List[float]] = Field(
        None,
        description = ""
    ),
    annot_ec_number_array: Optional[List[str]] = Field(
        None,
        description = ""
    )
