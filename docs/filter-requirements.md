# Filter Feature - Backend Requirements

## Overview

Backend API enhancements to support the filter feature on the database-search page. This includes two new endpoints and one modification to the existing search endpoint.

---

## Summary of Changes

| Change | Type | Description |
|--------|------|-------------|
| `GET /api/v1/curation-statuses` | New endpoint | Returns available curation status options |
| `GET /api/v1/typeahead` | Enhancement | Add search context params, pagination, and `predicted_ec` field |
| `curation_status` param on `/api/v1/search` | Enhancement | Adds curation status filtering to existing search |

---

## Enhancement: Typeahead Endpoint

### `GET /api/v1/typeahead`

Enhance the existing typeahead endpoint to support:
1. **Search context parameters** — Constrain results to current search/filter context
2. **Pagination** — Handle high-cardinality fields
3. **New field: `predicted_ec`** — Support EC number typeahead

### Updated Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `field_name` | string | No | Field to search. **Updated enum:** `accession`, `organism`, `protein_name`, `gene_name`, `uniprot_id`, `predicted_ec` (new). Default: `organism` |
| `search` | string | Yes | Search term (minimum 3 characters) |
| `limit` | integer | No | Maximum results per page. Default: `20` |
| `offset` | integer | No | Number of results to skip. Default: `0` |
| **Search context params** | | | |
| `accession` | array[string] | No | Filter by UniProt Accession |
| `organism` | array[string] | No | Filter by Organism |
| `protein` | array[string] | No | Filter by Protein Name |
| `gene_name` | array[string] | No | Filter by Gene Name |
| `uniprot` | array[string] | No | Filter by UniProt ID |
| `ec_number` | array[string] | No | Filter by predicted EC number |
| `curation_status` | array[string] | No | Filter by curation status |
| `clean_ec_confidence_min` | number | No | Minimum confidence score |
| `clean_ec_confidence_max` | number | No | Maximum confidence score |
| `sequence_length` | string | No | Minimum sequence length |

### Example Request

Typeahead for protein names within Homo sapiens records that have reviewed curation status:

```
GET /api/v1/typeahead?field_name=protein_name&search=Free&organism=Homo+sapiens&curation_status=reviewed&limit=20&offset=0
```

### Example Response

```json
{
  "field_name": "protein_name",
  "search": "Free",
  "search_context": {
    "organism": ["Homo sapiens"],
    "curation_status": ["reviewed"]
  },
  "total": 85,
  "limit": 20,
  "offset": 0,
  "matches": [
    "Free fatty acid receptor 1",
    "Free fatty acid receptor 2",
    "Free fatty acid receptor 3",
    "Free fatty acid receptor 4"
  ],
  "next": "/api/v1/typeahead?field_name=protein_name&search=Free&organism=Homo+sapiens&curation_status=reviewed&limit=20&offset=20",
  "previous": null
}
```

### Updated Response Schema

```yaml
CLEANTypeaheadResponse:
  type: object
  properties:
    field_name:
      type: string
      enum:
        - accession
        - organism
        - protein_name
        - gene_name
        - uniprot_id
        - predicted_ec
      description: The field that was searched
    search:
      type: string
      minLength: 3
      description: The search term used
    search_context:
      type: object
      additionalProperties: true
      description: Echo of search context parameters used to constrain results
    total:
      type: integer
      description: Total number of matches across all pages
    limit:
      type: integer
      description: Maximum results per page
      default: 20
    offset:
      type: integer
      description: Number of results skipped
      default: 0
    matches:
      type: array
      items:
        type: string
      description: List of matching values for this page
    next:
      anyOf:
        - type: string
        - type: 'null'
      description: URL for next page of results, or null if no more pages
    previous:
      anyOf:
        - type: string
        - type: 'null'
      description: URL for previous page of results, or null if on first page
  required:
    - field_name
    - search
    - total
    - limit
    - offset
    - matches
```

### Implementation Notes

**Search Context Filtering:**
- When search context params are provided, the typeahead query should only return values that exist within records matching those constraints
- Example: `?field_name=protein_name&search=Free&organism=Homo+sapiens` returns only protein names containing "Free" that appear in Homo sapiens records

**Predicted EC Field:**
- The `predicted_ec` field searches within the `predicted_ec[].ec_number` array
- Returns distinct EC numbers matching the search term

**Pagination:**
- Results should be sorted alphabetically for consistency
- `total` reflects the full count of matches, not just the current page
- `next` and `previous` URLs should include all original query parameters

**Backward Compatibility:**
- If no search context params or pagination params are provided, behavior matches existing endpoint
- New fields (`search_context`, `total`, `next`, `previous`) are additive

---

## New Endpoint: Curation Statuses

### `GET /api/v1/curation-statuses`

Returns the list of available curation status values for filtering.

### Request

No parameters required.

### Response

**Status:** `200 OK`

**Content-Type:** `application/json`

```json
{
  "statuses": [
    {
      "value": "reviewed",
      "label": "Reviewed (Swiss-Prot)"
    },
    {
      "value": "unreviewed",
      "label": "Unreviewed (TrEMBL)"
    }
  ]
}
```

### Response Schema

```yaml
CLEANCurationStatusResponse:
  type: object
  properties:
    statuses:
      type: array
      items:
        $ref: '#/components/schemas/CurationStatusOption'
      description: List of available curation status options

CurationStatusOption:
  type: object
  properties:
    value:
      type: string
      description: Value to use in API filter requests
    label:
      type: string
      description: Human-readable display label
  required:
    - value
    - label
```

### Notes

- This endpoint can return hardcoded values or query distinct values from the database
- Values should match exactly what is stored in the `curation_status` field
- Labels are for display purposes in the UI

---

## Enhancement: Search Endpoint

### `GET /api/v1/search`

Add `curation_status` as a new filter parameter.

### New Parameter

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `curation_status` | array[string] | No | Filter by curation status. Accepts multiple values (OR logic). |

### Valid Values

- `reviewed` — Reviewed (Swiss-Prot)
- `unreviewed` — Unreviewed (TrEMBL)

### Example Requests

Single value:
```
GET /api/v1/search?protein=Free+fatty+acid+receptor+2&curation_status=reviewed
```

Multiple values (OR logic):
```
GET /api/v1/search?protein=Free+fatty+acid+receptor+2&curation_status=reviewed&curation_status=unreviewed
```

### Filter Logic

- Multiple `curation_status` values use OR logic
- `curation_status` combined with other filters uses AND logic

**Example:**
```
GET /api/v1/search?organism=Homo+sapiens&curation_status=reviewed&clean_ec_confidence_min=0.8
```

Translates to:
```sql
WHERE organism = 'Homo sapiens'
  AND curation_status = 'reviewed'
  AND clean_ec_confidence >= 0.8
```

### Updated OpenAPI Spec Addition

```yaml
parameters:
  - name: curation_status
    in: query
    required: false
    schema:
      anyOf:
        - type: array
          items:
            type: string
            enum:
              - reviewed
              - unreviewed
        - type: 'null'
      description: Curation status filter
      title: Curation Status
    description: Filter by curation status (reviewed or unreviewed)
```

---

## Data Model Reference

For context, relevant fields from the existing `CLEANDataBase` schema:

```yaml
CLEANDataBase:
  properties:
    curation_status:
      anyOf:
        - type: string
        - type: 'null'
      title: Curation Status
      description: Status of the curation for the Uniprot record.
    
    predicted_ec:
      anyOf:
        - items:
            $ref: '#/components/schemas/ECNumberConfidence'
          type: array
        - type: 'null'
      title: Predicted Ec
      description: List of CLEAN predicted EC numbers with associated confidence scores.

ECNumberConfidence:
  properties:
    ec_number:
      type: string
      title: Ec Number
    score:
      type: number
      title: Score
  required:
    - ec_number
    - score
```

---

## Error Responses

All endpoints should return standard error responses:

### 422 Validation Error

```json
{
  "detail": [
    {
      "loc": ["query", "curation_status"],
      "msg": "Invalid curation status value",
      "type": "value_error"
    }
  ]
}
```

### 500 Internal Server Error

```json
{
  "detail": "Internal server error"
}
```

---

## Performance Considerations

### `/api/v1/typeahead` (Enhanced)

- Search context filtering adds query complexity; ensure proper indexing on all filterable fields
- For `predicted_ec` field, ensure index on `predicted_ec.ec_number` (JSON array field)
- Consider caching common search context + field combinations
- Pagination reduces payload size for high-cardinality fields
- Add database indexes for text search (prefix matching) on typeahead fields

### `/api/v1/search` with `curation_status`

- Add database index on `curation_status` column if not already present
- Monitor query performance after deployment

---

## Testing Requirements

### `/api/v1/typeahead` (Enhanced)

**Search Context:**
- Returns only values existing within constrained result set
- Multiple context params combine with AND logic
- Empty context returns matches from full database (backward compatible)

**Pagination:**
- Default limit is 20
- `offset` correctly skips results
- `total` reflects full match count
- `next`/`previous` URLs are correct and include all query params
- Last page has `next: null`
- First page has `previous: null`

**New Field (`predicted_ec`):**
- Returns distinct EC numbers matching search term
- Searches within `predicted_ec[].ec_number` array
- Respects search context constraints

**Backward Compatibility:**
- Existing calls without new params still work
- Response includes new fields without breaking existing clients

### `/api/v1/curation-statuses`

- Returns expected status options
- Response format matches schema

### `/api/v1/search` with `curation_status`

- Single curation_status value filters correctly
- Multiple curation_status values use OR logic
- Combines correctly with other filters (AND logic)
- Invalid curation_status value returns 422
- Null/missing curation_status returns all records (no filter)