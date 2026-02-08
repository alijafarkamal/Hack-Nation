"""Databricks Mosaic AI Vector Search SDK wrapper — RAG.

Performs semantic search over the description column of the Ghana
facilities Delta table using auto-generated embeddings.

Ref: https://docs.databricks.com/en/generative-ai/vector-search
"""

import mlflow

from src.config import VS_ENDPOINT, VS_INDEX, vs_client

# Column list to sync back from the index
_COLUMNS = [
    "name",
    "facilityTypeId",
    "address_city",
    "region_normalized",
    "specialties",
    "description",
    "capability",
    "procedure",
    "equipment",
]


@mlflow.trace(name="query_vector_search", span_type="RETRIEVER")
def query_vector_search(
    query_text: str,
    num_results: int = 10,
    filters: dict | None = None,
) -> list[dict]:
    """Semantic search over facility free-form text columns.

    Args:
        query_text: Natural language query for semantic matching.
        num_results: Number of top-k results to return.
        filters: Optional column filters (e.g., {"facilityTypeId": "hospital"}).

    Returns:
        List of dicts, each representing a matching facility record.
    """
    index = vs_client.get_index(endpoint_name=VS_ENDPOINT, index_name=VS_INDEX)

    kwargs = dict(
        query_text=query_text,
        columns=_COLUMNS,
        num_results=num_results,
    )
    if filters:
        kwargs["filters"] = filters

    raw = index.similarity_search(**kwargs)

    # Convert from data_array to list of dicts
    data_array = raw.get("result", {}).get("data_array", [])
    col_names = [c["name"] for c in raw.get("manifest", {}).get("columns", [])]

    return [dict(zip(col_names, row)) for row in data_array]
