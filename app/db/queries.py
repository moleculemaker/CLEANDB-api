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

    if params.clean_ec_confidence_min is not None:
        param_idx += 1
        param_name = f"param_{param_idx}"
        conditions.append(f"max_clean_ec_confidence > ${param_idx}")
        query_params[param_name] = params.clean_ec_confidence_min

    if params.clean_ec_confidence_max is not None:
        param_idx += 1
        param_name = f"param_{param_idx}"
        conditions.append(f"max_clean_ec_confidence < ${param_idx}")
        query_params[param_name] = params.clean_ec_confidence_max

    if params.sequence_length is not None:
        param_idx += 1
        param_name = f"param_{param_idx}"
        conditions.append(f"amino_acids >= ${param_idx}")
        query_params[param_name] = params.sequence_length

    if params.curation_status is not None:
        column_conditions = []
        for value in params.curation_status:
            param_idx += 1
            param_name = f"param_{param_idx}"
            column_conditions.append(f"LOWER(curation_status) = LOWER(${param_idx})")
            query_params[param_name] = value
        if column_conditions:
            conditions.append(f"({' OR '.join(column_conditions)})")

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
    ORDER BY puace.max_clean_ec_confidence DESC, pua.amino_acids ASC, pua.predictions_uniprot_annot_id ASC
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

def _has_search_context(params: CLEANTypeaheadQueryParams) -> bool:
    """Check if any search context filters are provided."""
    return any([
        params.accession,
        params.organism,
        params.protein_name,
        params.gene_name,
        params.uniprot_id,
        params.clean_ec_number,
        params.curation_status,
        params.clean_ec_confidence_min,
        params.clean_ec_confidence_max,
        params.sequence_length,
    ])


def _build_typeahead_context_conditions(
    params: CLEANTypeaheadQueryParams,
    start_param_idx: int = 1,
) -> Tuple[str, Dict[str, Any], int]:
    """Build SQL conditions from typeahead context parameters."""
    conditions = []
    query_params = {}
    param_idx = start_param_idx

    # Process string filters (case-insensitive exact matches with OR logic within columns)
    string_columns = {
        "accession": params.accession,
        "protein_name": params.protein_name,
        "organism": params.organism,
        "gene_name": params.gene_name,
        "uniprot_id": params.uniprot_id,
    }

    for column, values in string_columns.items():
        if values:
            column_conditions = []
            for value in values:
                param_idx += 1
                param_name = f"param_{param_idx}"
                if column == "accession":
                    column_conditions.append(f"pua.{column} = UPPER(${param_idx})")
                else:
                    column_conditions.append(f"LOWER(pua.{column}) = LOWER(${param_idx})")
                query_params[param_name] = value
            if column_conditions:
                conditions.append(f"({' OR '.join(column_conditions)})")

    if params.clean_ec_number is not None:
        column_conditions = []
        for value in params.clean_ec_number:
            param_idx += 1
            param_name = f"param_{param_idx}"
            if value.endswith("-"):
                column_conditions.append(f"puace.clean_ec_number LIKE ${param_idx}")
                query_params[param_name] = re.sub(r'-.*$', '%', value)
            else:
                column_conditions.append(f"puace.clean_ec_number = ${param_idx}")
                query_params[param_name] = value
        if column_conditions:
            conditions.append(f"({' OR '.join(column_conditions)})")

    if params.clean_ec_confidence_min is not None:
        param_idx += 1
        param_name = f"param_{param_idx}"
        conditions.append(f"puace.clean_ec_confidence > ${param_idx}")
        query_params[param_name] = params.clean_ec_confidence_min

    if params.clean_ec_confidence_max is not None:
        param_idx += 1
        param_name = f"param_{param_idx}"
        conditions.append(f"puace.clean_ec_confidence < ${param_idx}")
        query_params[param_name] = params.clean_ec_confidence_max

    if params.sequence_length is not None:
        param_idx += 1
        param_name = f"param_{param_idx}"
        conditions.append(f"pua.amino_acids >= ${param_idx}")
        query_params[param_name] = params.sequence_length

    if params.curation_status is not None:
        column_conditions = []
        for value in params.curation_status:
            param_idx += 1
            param_name = f"param_{param_idx}"
            column_conditions.append(f"LOWER(pua.curation_status) = LOWER(${param_idx})")
            query_params[param_name] = value
        if column_conditions:
            conditions.append(f"({' OR '.join(column_conditions)})")

    where_clause = " AND ".join(conditions) if conditions else "TRUE"
    return where_clause, query_params, param_idx


async def get_typeahead_suggestions(db: Database, params: CLEANTypeaheadQueryParams
) -> Tuple[List[str], int]:
    """Get typeahead suggestions based on the query parameters.

    Returns a tuple of (matches, total_count).
    """
    search = params.search.strip()
    if len(search) < 3:
        raise ValueError("Search term must be at least 3 characters long.")

    limit = params.limit or 20
    offset = params.offset or 0
    has_context = _has_search_context(params)

    # Field-specific configuration
    field_config = {
        'accession': {
            'search_pattern': lambda s: s + '%',  # match beginning
            'search_condition': 'pua.accession LIKE UPPER($1)',
            'mv_table': None,
            'mv_search_condition': None,
            'column': 'accession',
            'result_column': 'accession',
        },
        'organism': {
            'search_pattern': lambda s: '%' + s + '%',  # match anywhere
            'search_condition': 'LOWER(pua.organism) LIKE LOWER($1)',
            'mv_table': 'cleandb.predictions_uniprot_annot_mv01',
            'mv_search_condition': 'organism_lower LIKE LOWER($1)',
            'column': 'organism',
            'result_column': 'organism',
        },
        'protein_name': {
            'search_pattern': lambda s: '%' + s + '%',
            'search_condition': 'LOWER(pua.protein_name) LIKE LOWER($1)',
            'mv_table': 'cleandb.predictions_uniprot_annot_mv02',
            'mv_search_condition': 'protein_name_lower LIKE LOWER($1)',
            'column': 'protein_name',
            'result_column': 'protein_name',
        },
        'gene_name': {
            'search_pattern': lambda s: '%' + s + '%',
            'search_condition': 'LOWER(pua.gene_name) LIKE LOWER($1)',
            'mv_table': 'cleandb.predictions_uniprot_annot_mv03',
            'mv_search_condition': 'gene_name_lower LIKE LOWER($1)',
            'column': 'gene_name',
            'result_column': 'gene_name',
        },
        'uniprot_id': {
            'search_pattern': lambda s: '%' + s + '%',
            'search_condition': 'LOWER(pua.uniprot_id) LIKE LOWER($1)',
            'mv_table': None,
            'mv_search_condition': None,
            'column': 'uniprot_id',
            'result_column': 'uniprot_id',
        },
        'predicted_ec': {
            'search_pattern': lambda s: s + '%',  # match beginning of EC number
            'search_condition': 'puace.clean_ec_number LIKE $1',
            'mv_table': None,
            'mv_search_condition': None,
            'column': 'clean_ec_number',
            'result_column': 'clean_ec_number',
        },
    }

    if params.field_name not in field_config:
        raise ValueError(f"Invalid field name: {params.field_name}")

    config = field_config[params.field_name]
    search_term = config['search_pattern'](search)

    if not has_context:
        # No search context - use materialized views for better performance when available
        if params.field_name == 'predicted_ec':
            # Query the EC table directly
            count_query = f"""SELECT COUNT(DISTINCT clean_ec_number) FROM cleandb.predictions_uniprot_annot_clean_ec WHERE clean_ec_number LIKE $1"""
            data_query = f"""SELECT DISTINCT clean_ec_number FROM cleandb.predictions_uniprot_annot_clean_ec WHERE clean_ec_number LIKE $1 ORDER BY 1 ASC LIMIT {limit} OFFSET {offset}"""
        elif config['mv_table']:
            # Use materialized view
            count_query = f"""SELECT COUNT(DISTINCT {config['column']}) FROM {config['mv_table']} WHERE {config['mv_search_condition']}"""
            data_query = f"""SELECT DISTINCT {config['column']} FROM {config['mv_table']} WHERE {config['mv_search_condition']} ORDER BY 1 ASC LIMIT {limit} OFFSET {offset}"""
        else:
            # Query main table directly
            count_query = f"""SELECT COUNT(DISTINCT {config['column']}) FROM cleandb.predictions_uniprot_annot pua WHERE {config['search_condition']}"""
            data_query = f"""SELECT DISTINCT {config['column']} FROM cleandb.predictions_uniprot_annot pua WHERE {config['search_condition']} ORDER BY 1 ASC LIMIT {limit} OFFSET {offset}"""

        total = await db.fetchval(count_query, search_term)
        records = await db.fetch(data_query, search_term)
        return [record[config['result_column']] for record in records], total

    else:
        # Has search context - need to join with main table and apply filters
        context_where, context_params, param_idx = _build_typeahead_context_conditions(params, start_param_idx=1)

        # The search term will be $1, context params start from $2
        # Rebuild context conditions with offset
        context_where, context_params, _ = _build_typeahead_context_conditions(params, start_param_idx=1)

        # Build the query based on field type
        if params.field_name == 'predicted_ec':
            # Need to join with EC table
            base_query = f"""
                FROM cleandb.predictions_uniprot_annot pua
                INNER JOIN cleandb.predictions_uniprot_annot_clean_ec puace
                    ON puace.predictions_uniprot_annot_id = pua.predictions_uniprot_annot_id
                WHERE puace.clean_ec_number LIKE $1
                    AND {context_where}
            """
            select_column = "puace.clean_ec_number"
        else:
            # Check if we need to join with EC table for context filtering
            needs_ec_join = params.clean_ec_number is not None or params.clean_ec_confidence_min is not None or params.clean_ec_confidence_max is not None

            if needs_ec_join:
                base_query = f"""
                    FROM cleandb.predictions_uniprot_annot pua
                    INNER JOIN cleandb.predictions_uniprot_annot_clean_ec puace
                        ON puace.predictions_uniprot_annot_id = pua.predictions_uniprot_annot_id
                    WHERE {config['search_condition']}
                        AND {context_where}
                """
            else:
                base_query = f"""
                    FROM cleandb.predictions_uniprot_annot pua
                    WHERE {config['search_condition']}
                        AND {context_where}
                """
            select_column = f"pua.{config['column']}"

        count_query = f"SELECT COUNT(*) FROM (SELECT DISTINCT {select_column} {base_query}) sub"
        data_query = f"SELECT DISTINCT {select_column} {base_query} ORDER BY 1 ASC LIMIT {limit} OFFSET {offset}"

        # Build query args: search_term first, then context params
        query_args = [search_term] + list(context_params.values())

        total = await db.fetchval(count_query, *query_args)
        records = await db.fetch(data_query, *query_args)
        return [record[config['result_column']] for record in records], total

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