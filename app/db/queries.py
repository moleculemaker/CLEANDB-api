from typing import Any, Dict, List, Tuple

import rich
import re
from app.db.database import Database
from app.models.clean_data import CLEANColumn
from app.models.query_params import CLEANECLookupQueryParams, CLEANSearchQueryParams, CLEANTypeaheadQueryParams

async def build_conditions(
    params: CLEANSearchQueryParams,
) -> Tuple[str, Dict[str, Any]]:
    """Build SQL query conditions from query parameters."""
    conditions = []
    query_params = {}
    param_idx = 0

    # Process string filters (case-insensitive exact matches with OR logic within columns)
    string_columns = {
        "accession": params.accession,
        "protein_name": params.protein_name,
        "organism": params.organism,
        "gene_name": params.gene_name,
        "uniprot_id": params.uniprot_id,
    }

    for column, values in string_columns.items():
        rich.print(f"Processing column: {column} with values: {values}")
        if values:
            column_conditions = []

            for value in values:
                param_idx += 1
                param_name = f"param_{param_idx}"

                if column == "accession":
                    # accessions are stored and indexed in uppercase
                    column_conditions.append(f"{column} = UPPER(${param_idx})")
                    query_params[param_name] = value
                else:
                    column_conditions.append(f"LOWER({column}) = LOWER(${param_idx})")
                    query_params[param_name] = value

            if column_conditions:
                conditions.append(f"({' OR '.join(column_conditions)})")

    if params.clean_ec_number is not None:
        column_conditions = []

        for value in params.clean_ec_number:
            param_idx += 1
            param_name = f"param_{param_idx}"

            # for EC numbers, we allow dashes as wildcards matching the end of the string (e.g., "1.2.-.-"), which is the convention used in the ec_class_names table
            if value.endswith("-"):
                column_conditions.append(f"clean_ec_number LIKE ${param_idx}")
                query_params[param_name] = re.sub(r'-.*$', '%', value)
            else:
                column_conditions.append(f"clean_ec_number = ${param_idx}")
                query_params[param_name] = value
        if column_conditions:
            conditions.append(f"pua.predictions_uniprot_annot_id IN (SELECT predictions_uniprot_annot_id FROM cleandb.predictions_uniprot_annot_clean_ec WHERE " + " OR ".join(column_conditions) + ")")

    if params.clean_ec_confidence is not None:
        param_idx += 1
        param_name = f"param_{param_idx}"
        conditions.append(f"max_clean_ec_confidence > ${param_idx}")
        query_params[param_name] = params.clean_ec_confidence

    if params.sequence_length is not None:
        param_idx += 1
        param_name = f"param_{param_idx}"
        conditions.append(f"amino_acids >= ${param_idx}")
        query_params[param_name] = params.sequence_length

    # Combine all conditions with AND logic
    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    return where_clause, query_params

def get_query(columns_to_select: str, where_clause: str) -> str:
    return f"""
    SELECT
        {columns_to_select}
    FROM cleandb.predictions_uniprot_annot pua
    INNER JOIN cleandb.predictions_uniprot_annot_clean_ec_mv01 puace
        ON puace.predictions_uniprot_annot_id = pua.predictions_uniprot_annot_id
    LEFT JOIN cleandb.predictions_uniprot_annot_ec_mv01 puae
        ON puae.predictions_uniprot_annot_id = pua.predictions_uniprot_annot_id
    WHERE {where_clause}
    ORDER BY puace.max_clean_ec_confidence DESC
    """

async def get_filtered_data(
    db: Database, params: CLEANSearchQueryParams
) -> List[Dict[str, Any]]:
    """Get filtered data from the database."""
    where_clause, query_params = await build_conditions(params)

    columns_to_select = """
        pua.predictions_uniprot_annot_id,
        pua.uniprot_id,
        pua.curation_status,
        pua.accession,
        pua.protein_name,
        pua.organism,
        pua.ncbi_taxid,
        pua.amino_acids,
        pua.protein_sequence,
        pua.enzyme_function,
        pua.gene_name,
        puace.clean_ec_number_array,
        puace.clean_ec_confidence_array,
        puae.annot_ec_number_array
    """

    # Build the main query
    query = get_query(columns_to_select, where_clause)

    # Add pagination
    if params.limit is not None:
        query += f" LIMIT {params.limit}"

    if params.offset is not None:
        query += f" OFFSET {params.offset}"

    rich.print(f"{query=}")
    # Extract query parameters from the dictionary
    query_args = list(query_params.values())

    # Execute the query
    records = await db.fetch(query, *query_args)
    return records


async def get_total_count(db: Database, params: CLEANSearchQueryParams) -> int:
    """Get total count of records matching the filters."""
    where_clause, query_params = await build_conditions(params)

    query = get_query("COUNT(*)", where_clause)

    # Extract query parameters from the dictionary
    query_args = list(query_params.values())

    # Execute the query
    result = await db.fetchval(query, *query_args)
    return result

async def get_typeahead_suggestions(db: Database, params: CLEANTypeaheadQueryParams
) -> List[str]:
    """Get typeahead suggestions based on the query parameters."""
    search = params.search.strip()
    if len(search) < 3:
        raise ValueError("Search term must be at least 3 characters long.")

    if params.field_name == 'accession':
        # match the beginning of the string
        # accessions are stored and indexed in uppercase
        search += '%'
        query = f"""SELECT DISTINCT accession FROM cleandb.predictions_uniprot_annot WHERE accession LIKE UPPER($1) ORDER BY 1 ASC"""
    elif params.field_name == 'organism':
        search = '%' + search + '%'
        # match any part of the string
        query = f"""SELECT DISTINCT organism FROM cleandb.predictions_uniprot_annot_mv01 WHERE organism_lower LIKE LOWER($1) ORDER BY 1 ASC"""
    elif params.field_name == 'protein_name':
        # match any part of the string
        search = '%' + search + '%'
        query = f"""SELECT DISTINCT protein_name FROM cleandb.predictions_uniprot_annot_mv02 WHERE protein_name_lower LIKE LOWER($1) ORDER BY 1 ASC"""
    elif params.field_name == 'gene_name':
        # match any part of the string (note we have gene names that start with an apostrophe, for example, which the user might not expect)
        search = '%' + search + '%'
        query = f"""SELECT DISTINCT gene_name FROM cleandb.predictions_uniprot_annot_mv03 WHERE gene_name_lower LIKE LOWER($1) ORDER BY 1 ASC"""
    elif params.field_name == 'uniprot_id':
        search = '%' + search + '%'
        query = f"""SELECT DISTINCT uniprot_id FROM cleandb.predictions_uniprot_annot WHERE LOWER(uniprot_id) LIKE LOWER($1) ORDER BY 1 ASC"""
    else:
        raise ValueError(f"Invalid field name: {params.field_name}")

    query += f" LIMIT {params.limit or 10}"

    # Execute the query
    records = await db.fetch(query, search)
    return [record[params.field_name] for record in records]

async def get_ec_suggestions(db: Database, params: CLEANECLookupQueryParams
) -> List[Dict[str, str]]:
    """Look up EC numbers or names based on the query parameters."""
    search = params.search.strip()

    # match numbers at the beginning of the string
    number_search = search + '%'
    # match names anywhere in the string
    name_search = '%' + search + '%'
    query = f"""SELECT ec_number, ec_name FROM cleandb.ec_class_names WHERE ec_number LIKE $1 OR LOWER(ec_name) LIKE LOWER($2) ORDER BY 1 ASC"""
    query += f" LIMIT {params.limit or 10}"

    # Execute the query
    records = await db.fetch(query, number_search, name_search)
    return [{ 'ec_number': record['ec_number'], 'ec_name': record['ec_name'] } for record in records]