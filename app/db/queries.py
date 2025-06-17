from typing import Any, Dict, List, Tuple

import rich

from app.db.database import Database
from app.models.clean_data import CLEANColumn
from app.models.query_params import CLEANSearchQueryParams

async def build_ec_conditions(
    params: CLEANSearchQueryParams,
) -> Tuple[str, Dict[str, Any]]:
    """Build conditions for the filtered_clean_ec CTE."""
    conditions = []
    query_params = {}
    param_idx = 0

    if params.ec_number:
        ec_conditions = []
        for value in params.ec_number:
            param_idx += 1
            param_name = f"param_{param_idx}"
            if "%" in value:
                ec_conditions.append(f"clean_ec_number LIKE ${param_idx}")
            else:
                ec_conditions.append(f"clean_ec_number = ${param_idx}")
            query_params[param_name] = value
        conditions.append(f"({' OR '.join(ec_conditions)})")

    if params.ec_confidence is not None:
        param_idx += 1
        param_name = f"param_{param_idx}"
        conditions.append(f"clean_ec_confidence > ${param_idx}")
        query_params[param_name] = params.ec_confidence

    where_clause = " AND ".join(conditions) if conditions else "TRUE"
    return where_clause, query_params

async def build_base_conditions(
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
    }

    for column, values in string_columns.items():
        if values:
            column_conditions = []

            for value in values:
                param_idx += 1
                param_name = f"param_{param_idx}"

                # Special handling for EC number with wildcard support
                if column == "ec_number" and "%" in value:
                    column_conditions.append(f"{column} LIKE ${param_idx}")
                else:
                    column_conditions.append(f"LOWER({column}) = LOWER(${param_idx})")

                query_params[param_name] = value

            if column_conditions:
                conditions.append(f"({' OR '.join(column_conditions)})")

    # Combine all conditions with AND logic
    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    return where_clause, query_params

def get_query(columns_to_select: str, ec_where_clause: str, base_where_clause: str) -> str: 
    return f"""
    WITH filtered_clean_ec AS (
        SELECT
            predictions_uniprot_annot_id,
            clean_ec_number,
            clean_ec_confidence
        FROM cleandb.predictions_uniprot_annot_clean_ec
        WHERE {ec_where_clause}
    ),
    clean_aggregated AS (
        SELECT
            predictions_uniprot_annot_id,
            array_agg(clean_ec_number) AS clean_ec_number_array,
            array_agg(clean_ec_confidence) AS clean_ec_confidence_array
        FROM filtered_clean_ec
        GROUP BY predictions_uniprot_annot_id
    ),
    annot_ec_aggregated AS (
        SELECT
            pec.predictions_uniprot_annot_id,
            array_agg(pec.ec_number) AS annot_ec_number_array
        FROM cleandb.predictions_uniprot_annot_ec pec
        INNER JOIN filtered_clean_ec fce
            ON fce.predictions_uniprot_annot_id = pec.predictions_uniprot_annot_id
        GROUP BY pec.predictions_uniprot_annot_id
    )
    SELECT
        {columns_to_select}
    FROM cleandb.predictions_uniprot_annot pua
    INNER JOIN clean_aggregated ca
        ON ca.predictions_uniprot_annot_id = pua.predictions_uniprot_annot_id
    LEFT JOIN annot_ec_aggregated aea
        ON aea.predictions_uniprot_annot_id = pua.predictions_uniprot_annot_id
    WHERE {base_where_clause}
    """

async def get_filtered_data(
    db: Database, params: CLEANSearchQueryParams
) -> List[Dict[str, Any]]:
    """Get filtered data from the database."""
    ec_where_clause, ec_query_params = await build_ec_conditions(params)
    base_where_clause, base_query_params = await build_base_conditions(params)

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
        ca.clean_ec_number_array,
        ca.clean_ec_confidence_array,
        aea.annot_ec_number_array
    """


    # Build the main query
    query = get_query(columns_to_select, ec_where_clause, base_where_clause)

    # Add pagination
    if params.limit is not None:
        query += f" LIMIT {params.limit}"

    if params.offset is not None:
        query += f" OFFSET {params.offset}"

    rich.print(f"{query=}")
    # Extract query parameters from the dictionary
    query_args = list(ec_query_params.values()) + list(base_query_params.values())

    # Execute the query
    records = await db.fetch(query, *query_args)
    rich.print(f"{records=}")
    return records


async def get_total_count(db: Database, params: CLEANSearchQueryParams) -> int:
    """Get total count of records matching the filters."""
    ec_where_clause, ec_query_params = await build_ec_conditions(params)
    base_where_clause, base_query_params = await build_base_conditions(params)

    query = get_query("COUNT(*)", ec_where_clause, base_where_clause)

    # Extract query parameters from the dictionary
    query_args = list(ec_query_params.values()) + list(base_query_params.values())

    # Execute the query
    result = await db.fetchval(query, *query_args)
    return result
